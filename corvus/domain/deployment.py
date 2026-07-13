from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


def _now_utc() -> datetime:
    return datetime.now(UTC)


class AuthorityMode(StrEnum):
    EMBEDDED_LOCAL = "embedded_local"
    LOCAL_DAEMON = "local_daemon"
    SELF_HOSTED = "self_hosted"
    VENDOR_CLOUD = "vendor_cloud"


class AuthProfile(StrEnum):
    LOCAL_OS = "local_os"
    LOCAL_SESSION = "local_session"
    OIDC = "oidc"


class NetworkProfile(StrEnum):
    IN_PROCESS = "in_process"
    LOOPBACK = "loopback"
    NETWORK_TLS = "network_tls"


class StorageProfile(StrEnum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class ConfigurationContractError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


class DeploymentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    authority_mode: AuthorityMode
    auth_profile: AuthProfile
    network_profile: NetworkProfile
    storage_profile: StorageProfile
    enabled_adapters: frozenset[Literal["cli", "desktop", "web", "channel"]]
    protocol_version: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)


def validate_configuration_combination(
    profile: DeploymentProfile,
    workspace: object,
    placement: object,
) -> None:
    from corvus.domain.execution import ExecutionKind, ExecutionPlacement
    from corvus.domain.workspace import CollaborationMode, WorkspaceConfig

    if not isinstance(workspace, WorkspaceConfig):
        raise TypeError("workspace must be a WorkspaceConfig")
    if not isinstance(placement, ExecutionPlacement):
        raise TypeError("placement must be an ExecutionPlacement")
    if profile.authority_mode is AuthorityMode.EMBEDDED_LOCAL and (
        workspace.collaboration_mode is CollaborationMode.TEAM
    ):
        raise ConfigurationContractError(
            "embedded_local_requires_individual_workspace",
            "embedded-local authority cannot host a team workspace",
        )
    if (
        profile.authority_mode is AuthorityMode.VENDOR_CLOUD
        and profile.storage_profile is not StorageProfile.POSTGRESQL
    ):
        raise ConfigurationContractError(
            "vendor_cloud_requires_postgresql",
            "vendor-cloud authority requires PostgreSQL storage",
        )
    if (
        profile.authority_mode is AuthorityMode.EMBEDDED_LOCAL
        and placement.kind is not ExecutionKind.LOCAL_RUNNER
    ):
        raise ConfigurationContractError(
            "embedded_local_requires_local_runner",
            "embedded-local authority requires local-runner execution",
        )


class AuthorityCommitState(StrEnum):
    PREPARED = "prepared"
    ANCHOR_RESERVED = "anchor_reserved"
    DB_COMMITTED = "db_committed"
    ANCHOR_FINALIZED = "anchor_finalized"
    QUARANTINED = "quarantined"


class AuthorityCommitIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    epoch: int = Field(ge=1)
    deployment_instance_id: UUID
    prior_generation: int = Field(ge=0)
    next_generation: int = Field(ge=1)
    prior_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    mutation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposed_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: AuthorityCommitState
    created_at: datetime = Field(default_factory=_now_utc)

    @model_validator(mode="after")
    def validate_authority_advance(self) -> AuthorityCommitIntent:
        if self.proposed_state_root == self.prior_state_root:
            raise PydanticCustomError(
                "authority_root_not_advanced",
                "reason_code={reason_code}",
                {"reason_code": "authority_root_must_advance"},
            )
        if self.next_generation != self.prior_generation + 1:
            raise PydanticCustomError(
                "authority_generation_not_advanced",
                "reason_code={reason_code}",
                {"reason_code": "authority_generation_must_advance_once"},
            )
        return self


class AuthorityContractError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


class AuthorityRegistryTrustState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: UUID
    metadata_version: int = Field(ge=1)
    latest_verifier_key_version: int = Field(ge=1)
    complete_history_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: datetime
    expires_at: datetime
    offline_root_version: int = Field(ge=1)
    threshold_signature_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_metadata_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @property
    def canonical_digest(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json", exclude_none=True),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class CoverageKind(StrEnum):
    IN_ROOT = "in_root"
    EXTERNAL_PROOF = "external_proof"


class ManifestStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class AuthorityStateRootManifestVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    schema_version: int = Field(ge=1)
    canonicalization_version: int = Field(ge=1)
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ManifestStatus = ManifestStatus.ACTIVE
    created_at: datetime = Field(default_factory=_now_utc)


class AuthorityStateRootLeafFamily(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    manifest_version_id: UUID
    ordinal: int = Field(ge=1)
    family_name: str = Field(min_length=1, max_length=200)
    coverage_kind: CoverageKind
    external_proof_kind: str | None = Field(default=None, max_length=200)
    canonicalization_version: int = Field(ge=1)


class AuthorityRegistryFreshnessProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    registry_id: UUID
    trust_state_metadata_version: int = Field(ge=1)
    complete_history_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_sequence: int = Field(ge=1)
    challenge_nonce_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: datetime
    expires_at: datetime
    verifier_key_version_id: UUID
    registry_signature: str = Field(min_length=1)


def validate_authority_root_manifest(
    manifest: AuthorityStateRootManifestVersion,
    families: list[AuthorityStateRootLeafFamily],
    *,
    mutable_authority_families: set[str],
) -> None:
    listed = {family.family_name for family in families}
    if not mutable_authority_families <= listed:
        raise AuthorityContractError(
            "unlisted_authority_family",
            "one or more mutable authority families are absent from the manifest",
        )


def validate_registry_freshness_proof(
    proof: AuthorityRegistryFreshnessProof,
    trust_state: AuthorityRegistryTrustState,
    *,
    now: datetime,
    minimum_sequence: int,
    expected_nonce_digest: str,
) -> None:
    if proof.registry_sequence <= minimum_sequence:
        raise AuthorityContractError(
            "registry_sequence_replay",
            "registry freshness sequence did not advance",
        )
    if proof.challenge_nonce_digest != expected_nonce_digest:
        raise AuthorityContractError(
            "registry_nonce_mismatch",
            "registry freshness proof does not bind the caller nonce",
        )


def validate_registry_trust_transition(
    previous: AuthorityRegistryTrustState,
    current: AuthorityRegistryTrustState,
    *,
    now: datetime,
) -> None:
    if current.metadata_version != previous.metadata_version + 1:
        raise AuthorityContractError(
            "registry_metadata_version_skipped",
            "registry trust metadata must advance exactly one version",
        )
    if current.previous_metadata_digest != previous.canonical_digest:
        raise AuthorityContractError(
            "registry_metadata_prefix_mismatch",
            "registry trust metadata does not bind its exact predecessor",
        )
    if current.expires_at <= now:
        raise AuthorityContractError(
            "registry_trust_state_expired",
            "registry trust metadata is expired",
        )


class RestoreDecision(StrEnum):
    READ_QUEUE_ONLY = "read_queue_only"
    EXCLUSIVE_TAKEOVER_NEW_EPOCH = "exclusive_takeover_new_epoch"


class RestoreValidationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    restored_database_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_epoch: int = Field(ge=1)
    observed_generation: int = Field(ge=0)
    observed_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    trust_anchor_id: UUID
    former_instance_revocation_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    takeover_lease_or_local_anchor_receipt_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    decision: RestoreDecision = RestoreDecision.READ_QUEUE_ONLY
    reason_code: str = Field(min_length=1, max_length=200)
    validated_at: datetime = Field(default_factory=_now_utc)

    @model_validator(mode="after")
    def validate_takeover_evidence(self) -> RestoreValidationReceipt:
        if self.decision is RestoreDecision.EXCLUSIVE_TAKEOVER_NEW_EPOCH and (
            self.former_instance_revocation_digest is None
            or self.takeover_lease_or_local_anchor_receipt_digest is None
        ):
            raise PydanticCustomError(
                "unsafe_restore_takeover",
                "reason_code={reason_code}",
                {"reason_code": "takeover_requires_revocation_and_exclusive_receipt"},
            )
        return self
