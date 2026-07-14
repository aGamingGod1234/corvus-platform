from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from corvus.database import M1_AUTHORITY_FAMILY_NAMES
from corvus.domain.deployment import (
    AuthorityStateRootCalculation,
    AuthorityStateRootLeafCommitment,
    AuthorityStateRootManifestVersion,
    CoverageKind,
    ManifestStatus,
    canonical_authority_leaf_digest,
    canonical_authority_root_digest,
    validate_authority_family_commitments,
)
from corvus.infrastructure.repositories.registry import RegistryManifestRepository

_GLOBAL_FAMILIES = frozenset(
    {
        "authority_registries",
        "authority_registry_freshness_proofs",
        "authority_registry_trust_states",
        "authority_registry_verifier_keys",
        "authority_state_root_manifests",
    }
)
_SELF_REFERENTIAL_FIELDS = {
    "authority_commit_intents": frozenset({"proposed_state_root", "state"}),
    "idempotency_envelopes": frozenset({"status", "result_digest", "result_ref", "completed_at"}),
    "workspace_authorities": frozenset({"authority_state_root"}),
}
_VERSION_MARKERS = ("version", "sequence", "generation")
_FAMILY_SELECT_ALL = {
    "access_bundles": "SELECT * FROM access_bundles",
    "agent_grants": "SELECT * FROM agent_grants",
    "agent_identities": "SELECT * FROM agent_identities",
    "audience_policy_snapshots": "SELECT * FROM audience_policy_snapshots",
    "audit_anchor_recovery_checkpoints": "SELECT * FROM audit_anchor_recovery_checkpoints",
    "audit_receipts": "SELECT * FROM audit_receipts",
    "audit_result_bindings": "SELECT * FROM audit_result_bindings",
    "authority_close_certificates": "SELECT * FROM authority_close_certificates",
    "authority_commit_intents": "SELECT * FROM authority_commit_intents",
    "authority_epoch_credentials": "SELECT * FROM authority_epoch_credentials",
    "authority_handoff_activations": "SELECT * FROM authority_handoff_activations",
    "authority_handoffs": "SELECT * FROM authority_handoffs",
    "authority_registries": "SELECT * FROM authority_registries",
    "authority_registry_freshness_proofs": ("SELECT * FROM authority_registry_freshness_proofs"),
    "authority_registry_trust_states": "SELECT * FROM authority_registry_trust_states",
    "authority_registry_verifier_keys": "SELECT * FROM authority_registry_verifier_keys",
    "authority_state_root_manifests": "SELECT * FROM authority_state_root_manifests",
    "authority_trust_anchors": "SELECT * FROM authority_trust_anchors",
    "authorization_decision_snapshots": "SELECT * FROM authorization_decision_snapshots",
    "capability_grants": "SELECT * FROM capability_grants",
    "delegation_grants": "SELECT * FROM delegation_grants",
    "deployment_instance_leases": "SELECT * FROM deployment_instance_leases",
    "deployment_instances": "SELECT * FROM deployment_instances",
    "idempotency_envelopes": "SELECT * FROM idempotency_envelopes",
    "identity_workspaces": "SELECT * FROM identity_workspaces",
    "principals": "SELECT * FROM principals",
    "projects": "SELECT * FROM projects",
    "restore_validation_receipts": "SELECT * FROM restore_validation_receipts",
    "scopes": "SELECT * FROM scopes",
    "workspace_authorities": "SELECT * FROM workspace_authorities",
    "workspace_memberships": "SELECT * FROM workspace_memberships",
    "workspace_signing_key_versions": "SELECT * FROM workspace_signing_key_versions",
}
if frozenset(_FAMILY_SELECT_ALL) != M1_AUTHORITY_FAMILY_NAMES:
    raise RuntimeError("authority root query allowlist does not match the active manifest families")


class AuthorityRootCalculationError(RuntimeError):
    pass


class AuthorityRootCalculator:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.registry = RegistryManifestRepository(database)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def calculate(
        self,
        *,
        workspace_id: UUID,
        authority_generation: int,
        prospective_family_rows: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
        external_proof_digests: Mapping[str, str] | None = None,
    ) -> AuthorityStateRootCalculation:
        if authority_generation < 0:
            raise AuthorityRootCalculationError("authority_generation_invalid")
        replacements = dict(prospective_family_rows or {})
        unknown_replacements = set(replacements) - M1_AUTHORITY_FAMILY_NAMES
        if unknown_replacements:
            raise AuthorityRootCalculationError("authority_projection_family_unknown")

        manifest = self._latest_active_manifest()
        families = self.registry.list_manifest_families(manifest.id)
        if {family.family_name for family in families} != M1_AUTHORITY_FAMILY_NAMES:
            raise AuthorityRootCalculationError("authority_manifest_family_set_mismatch")

        supplied_proofs = dict(external_proof_digests or {})
        external_names = {
            family.family_name
            for family in families
            if family.coverage_kind is CoverageKind.EXTERNAL_PROOF
        }
        if set(supplied_proofs) - external_names:
            raise AuthorityRootCalculationError("authority_external_proof_family_unknown")
        if external_names - set(supplied_proofs):
            raise AuthorityRootCalculationError("authority_external_proof_missing")
        if any(
            len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest)
            for digest in supplied_proofs.values()
        ):
            raise AuthorityRootCalculationError("authority_external_proof_digest_invalid")

        commitments: list[AuthorityStateRootLeafCommitment] = []
        observed: dict[str, str] = {}
        for family in sorted(families, key=lambda item: item.ordinal):
            external_proof_digest = (
                supplied_proofs[family.family_name]
                if family.coverage_kind is CoverageKind.EXTERNAL_PROOF
                else None
            )
            if external_proof_digest is not None:
                rows: Sequence[Mapping[str, Any]] = ()
                records: tuple[Mapping[str, Any], ...] = (
                    {"external_proof_digest": external_proof_digest},
                )
            else:
                rows = (
                    self._validated_replacement_rows(
                        workspace_id,
                        family.family_name,
                        replacements[family.family_name],
                    )
                    if family.family_name in replacements
                    else self.project_family_rows(
                        workspace_id=workspace_id,
                        family_name=family.family_name,
                    )
                )
                records = self._canonical_records(family.family_name, rows)
            leaf_digest = canonical_authority_leaf_digest(
                family_name=family.family_name,
                canonicalization_version=family.canonicalization_version,
                records=records,
            )
            observed[family.family_name] = leaf_digest
            commitments.append(
                AuthorityStateRootLeafCommitment(
                    manifest_version_id=manifest.id,
                    authority_generation=authority_generation,
                    ordinal=family.ordinal,
                    family_name=family.family_name,
                    record_version=self._record_version(rows),
                    leaf_digest=leaf_digest,
                    external_proof_digest=external_proof_digest,
                )
            )

        validate_authority_family_commitments(
            manifest,
            families,
            commitments,
            observed_leaf_digests=observed,
        )
        root_digest = canonical_authority_root_digest(
            workspace_id=workspace_id,
            manifest=manifest,
            authority_generation=authority_generation,
            commitments=commitments,
        )
        return AuthorityStateRootCalculation(
            workspace_id=workspace_id,
            manifest=manifest,
            authority_generation=authority_generation,
            commitments=tuple(commitments),
            observed_leaf_digests=observed,
            root_digest=root_digest,
        )

    def verify_live_root(
        self,
        *,
        workspace_id: UUID,
        authority_generation: int,
        expected_root: str,
    ) -> AuthorityStateRootCalculation:
        stored = self.registry.list_leaf_commitments(
            workspace_id=workspace_id,
            authority_generation=authority_generation,
        )
        if not stored:
            raise AuthorityRootCalculationError("authority_commitments_missing")
        external_proofs = {
            commitment.family_name: commitment.external_proof_digest
            for commitment in stored
            if commitment.external_proof_digest is not None
        }
        calculation = self.calculate(
            workspace_id=workspace_id,
            authority_generation=authority_generation,
            external_proof_digests=external_proofs,
        )
        stored_by_family = {item.family_name: item for item in stored}
        if set(stored_by_family) != set(calculation.observed_leaf_digests):
            raise AuthorityRootCalculationError("authority_commitment_family_set_mismatch")
        if any(
            stored_by_family[family].leaf_digest != digest
            for family, digest in calculation.observed_leaf_digests.items()
        ):
            raise AuthorityRootCalculationError("authority_live_family_rollback_detected")
        if calculation.root_digest != expected_root:
            raise AuthorityRootCalculationError("authority_live_root_mismatch")
        return calculation

    def project_family_rows(
        self,
        *,
        workspace_id: UUID,
        family_name: str,
    ) -> tuple[dict[str, Any], ...]:
        if family_name not in M1_AUTHORITY_FAMILY_NAMES:
            raise AuthorityRootCalculationError("authority_projection_family_unknown")
        with self._connect() as connection:
            columns = self._table_columns(connection, family_name)
            rows = connection.execute(_FAMILY_SELECT_ALL[family_name]).fetchall()
            if "workspace_id" in columns:
                rows = [row for row in rows if row["workspace_id"] == str(workspace_id)]
            elif family_name == "identity_workspaces":
                rows = [row for row in rows if row["id"] == str(workspace_id)]
            elif family_name == "principals":
                principal_ids = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT principal_id FROM workspace_memberships WHERE workspace_id = ?",
                        (str(workspace_id),),
                    ).fetchall()
                }
                rows = [row for row in rows if row["id"] in principal_ids]
            elif family_name == "deployment_instances":
                instance_ids = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT deployment_instance_id FROM workspace_authorities "
                        "WHERE workspace_id = ? "
                        "UNION SELECT deployment_instance_id FROM deployment_instance_leases "
                        "WHERE workspace_id = ? "
                        "UNION SELECT deployment_instance_id FROM authority_epoch_credentials "
                        "WHERE workspace_id = ? "
                        "UNION SELECT deployment_instance_id FROM authority_commit_intents "
                        "WHERE workspace_id = ? "
                        "UNION SELECT target_deployment_instance_id "
                        "FROM authority_handoff_activations WHERE workspace_id = ? "
                        "UNION SELECT source_deployment_instance_id "
                        "FROM authority_close_certificates WHERE workspace_id = ?",
                        (str(workspace_id),) * 6,
                    ).fetchall()
                }
                rows = [row for row in rows if row["id"] in instance_ids]
            elif family_name not in _GLOBAL_FAMILIES:
                raise AuthorityRootCalculationError("authority_projection_rule_missing")
        return tuple(dict(row) for row in rows)

    def _latest_active_manifest(self) -> AuthorityStateRootManifestVersion:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM authority_state_root_manifests WHERE status = ? "
                "ORDER BY schema_version DESC, id DESC LIMIT 1",
                (ManifestStatus.ACTIVE.value,),
            ).fetchone()
        if row is None:
            raise AuthorityRootCalculationError("authority_manifest_missing")
        manifest = self.registry.get_manifest(UUID(str(row[0])))
        if manifest is None:
            raise AuthorityRootCalculationError("authority_manifest_missing")
        return manifest

    def _validated_replacement_rows(
        self,
        workspace_id: UUID,
        family_name: str,
        rows: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        with self._connect() as connection:
            expected_columns = set(self._table_columns(connection, family_name))
        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized_row = dict(row)
            if set(normalized_row) != expected_columns:
                raise AuthorityRootCalculationError("authority_projection_columns_mismatch")
            if "workspace_id" in expected_columns and normalized_row["workspace_id"] != str(
                workspace_id
            ):
                raise AuthorityRootCalculationError("authority_projection_workspace_mismatch")
            if family_name == "identity_workspaces" and normalized_row["id"] != str(workspace_id):
                raise AuthorityRootCalculationError("authority_projection_workspace_mismatch")
            normalized.append(normalized_row)
        return tuple(normalized)

    @staticmethod
    def _table_columns(connection: sqlite3.Connection, family_name: str) -> tuple[str, ...]:
        columns = tuple(
            str(row[1]) for row in connection.execute(f'PRAGMA table_info("{family_name}")')
        )
        if not columns:
            raise AuthorityRootCalculationError("authority_projection_table_missing")
        return columns

    @staticmethod
    def _canonical_records(
        family_name: str,
        rows: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        excluded = _SELF_REFERENTIAL_FIELDS.get(family_name, frozenset())
        canonical: list[dict[str, Any]] = []
        for row in rows:
            payload: dict[str, Any] | None = None
            payload_json = row.get("payload_json")
            if payload_json is not None:
                try:
                    parsed = json.loads(str(payload_json))
                except (TypeError, ValueError) as exc:
                    raise AuthorityRootCalculationError(
                        "authority_projection_payload_invalid"
                    ) from exc
                if not isinstance(parsed, dict):
                    raise AuthorityRootCalculationError("authority_projection_payload_invalid")
                payload = {key: value for key, value in parsed.items() if key not in excluded}
            columns = {
                key: value
                for key, value in row.items()
                if key != "payload_json" and key not in excluded
            }
            canonical.append({"columns": columns, "payload": payload})
        canonical.sort(
            key=lambda value: json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return tuple(canonical)

    @staticmethod
    def _record_version(rows: Sequence[Mapping[str, Any]]) -> int:
        versions = [
            int(value)
            for row in rows
            for key, value in row.items()
            if value is not None
            and isinstance(value, int)
            and any(marker in key for marker in _VERSION_MARKERS)
        ]
        return max(versions, default=1)
