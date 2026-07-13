from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from corvus.domain.audit import (
    AuditReceipt,
    AuthorizationDecisionSnapshot,
    SigningKeyStatus,
    WorkspaceSigningKeyVersion,
    validate_signing_time,
)
from corvus.domain.deployment import (
    AuthorityCloseCertificate,
    AuthorityCommitIntent,
    AuthorityCommitState,
    AuthorityContractError,
    AuthorityHandoffActivation,
    AuthorityRegistryFreshnessProof,
    AuthorityRegistryTrustState,
    AuthorityStateRootLeafFamily,
    AuthorityStateRootManifestVersion,
    CoverageKind,
    EpochKeyDisposition,
    RestoreDecision,
    RestoreValidationReceipt,
    validate_authority_root_manifest,
    validate_handoff_activation,
    validate_registry_freshness_proof,
    validate_registry_trust_transition,
)


def test_authority_commit_intent_requires_generation_and_root_advance() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuthorityCommitIntent(
            workspace_id=uuid4(),
            epoch=1,
            deployment_instance_id=uuid4(),
            prior_generation=4,
            next_generation=5,
            prior_state_root="a" * 64,
            mutation_digest="b" * 64,
            proposed_state_root="a" * 64,
            state=AuthorityCommitState.PREPARED,
        )

    assert exc_info.value.errors()[0]["ctx"]["reason_code"] == "authority_root_must_advance"


def test_restore_cannot_recreate_mutation_authority() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RestoreValidationReceipt(
            workspace_id=uuid4(),
            restored_database_digest="a" * 64,
            observed_epoch=4,
            observed_generation=12,
            observed_state_root="b" * 64,
            trust_anchor_id=uuid4(),
            decision=RestoreDecision.EXCLUSIVE_TAKEOVER_NEW_EPOCH,
            reason_code="operator_requested_takeover",
        )

    assert exc_info.value.errors()[0]["ctx"]["reason_code"] == (
        "takeover_requires_revocation_and_exclusive_receipt"
    )


def test_registry_trust_state_rejects_skipped_metadata_version() -> None:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    registry_id = uuid4()
    previous = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=3,
        latest_verifier_key_version=2,
        complete_history_head_digest="a" * 64,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        offline_root_version=1,
        threshold_signature_set_digest="b" * 64,
    )
    current = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=5,
        latest_verifier_key_version=3,
        complete_history_head_digest="c" * 64,
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        offline_root_version=1,
        threshold_signature_set_digest="d" * 64,
        previous_metadata_digest=previous.canonical_digest,
    )

    with pytest.raises(AuthorityContractError) as exc_info:
        validate_registry_trust_transition(previous, current, now=now)

    assert exc_info.value.reason_code == "registry_metadata_version_skipped"


def test_registry_trust_state_rejects_history_prefix_substitution() -> None:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    registry_id = uuid4()
    previous = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=3,
        latest_verifier_key_version=2,
        complete_history_head_digest="a" * 64,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        offline_root_version=1,
        threshold_signature_set_digest="b" * 64,
    )
    substituted = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=4,
        latest_verifier_key_version=3,
        complete_history_head_digest="c" * 64,
        issued_at=now,
        expires_at=now + timedelta(hours=2),
        offline_root_version=1,
        threshold_signature_set_digest="d" * 64,
        previous_metadata_digest="e" * 64,
    )

    with pytest.raises(AuthorityContractError) as exc_info:
        validate_registry_trust_transition(previous, substituted, now=now)

    assert exc_info.value.reason_code == "registry_metadata_prefix_mismatch"


def test_registry_trust_state_rejects_expired_metadata() -> None:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    registry_id = uuid4()
    previous = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=3,
        latest_verifier_key_version=2,
        complete_history_head_digest="a" * 64,
        issued_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        offline_root_version=1,
        threshold_signature_set_digest="b" * 64,
    )
    expired = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=4,
        latest_verifier_key_version=3,
        complete_history_head_digest="c" * 64,
        issued_at=now - timedelta(minutes=5),
        expires_at=now,
        offline_root_version=1,
        threshold_signature_set_digest="d" * 64,
        previous_metadata_digest=previous.canonical_digest,
    )

    with pytest.raises(AuthorityContractError) as exc_info:
        validate_registry_trust_transition(previous, expired, now=now)

    assert exc_info.value.reason_code == "registry_trust_state_expired"


def test_registry_freshness_proof_rejects_sequence_replay() -> None:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    registry_id = uuid4()
    trust_state = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=4,
        latest_verifier_key_version=3,
        complete_history_head_digest="a" * 64,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        offline_root_version=1,
        threshold_signature_set_digest="b" * 64,
    )
    proof = AuthorityRegistryFreshnessProof(
        registry_id=registry_id,
        trust_state_metadata_version=4,
        complete_history_head_digest="a" * 64,
        registry_sequence=9,
        challenge_nonce_digest="c" * 64,
        response_digest="d" * 64,
        issued_at=now - timedelta(seconds=5),
        expires_at=now + timedelta(minutes=5),
        verifier_key_version_id=uuid4(),
        registry_signature="signed-proof",
    )

    with pytest.raises(AuthorityContractError) as exc_info:
        validate_registry_freshness_proof(
            proof,
            trust_state,
            now=now,
            minimum_sequence=9,
            expected_nonce_digest="c" * 64,
        )

    assert exc_info.value.reason_code == "registry_sequence_replay"


def test_registry_freshness_proof_rejects_nonce_replay() -> None:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    registry_id = uuid4()
    trust_state = AuthorityRegistryTrustState(
        registry_id=registry_id,
        metadata_version=4,
        latest_verifier_key_version=3,
        complete_history_head_digest="a" * 64,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        offline_root_version=1,
        threshold_signature_set_digest="b" * 64,
    )
    proof = AuthorityRegistryFreshnessProof(
        registry_id=registry_id,
        trust_state_metadata_version=4,
        complete_history_head_digest="a" * 64,
        registry_sequence=10,
        challenge_nonce_digest="c" * 64,
        response_digest="d" * 64,
        issued_at=now - timedelta(seconds=5),
        expires_at=now + timedelta(minutes=5),
        verifier_key_version_id=uuid4(),
        registry_signature="signed-proof",
    )

    with pytest.raises(AuthorityContractError) as exc_info:
        validate_registry_freshness_proof(
            proof,
            trust_state,
            now=now,
            minimum_sequence=9,
            expected_nonce_digest="e" * 64,
        )

    assert exc_info.value.reason_code == "registry_nonce_mismatch"


def test_authority_root_manifest_rejects_unlisted_family() -> None:
    manifest = AuthorityStateRootManifestVersion(
        schema_version=1,
        canonicalization_version=1,
        manifest_digest="a" * 64,
    )
    listed = AuthorityStateRootLeafFamily(
        manifest_version_id=manifest.id,
        ordinal=1,
        family_name="workspace_memberships",
        coverage_kind=CoverageKind.IN_ROOT,
        canonicalization_version=1,
    )

    with pytest.raises(AuthorityContractError) as exc_info:
        validate_authority_root_manifest(
            manifest,
            [listed],
            mutable_authority_families={"workspace_memberships", "access_bundles"},
        )

    assert exc_info.value.reason_code == "unlisted_authority_family"


def test_audit_receipt_cannot_include_resulting_authority_state() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditReceipt.model_validate(
            {
                "workspace_id": str(uuid4()),
                "workspace_sequence": 1,
                "schema_version": 1,
                "prior_authority_epoch": 1,
                "prior_authority_generation": 4,
                "prior_authority_state_root": "a" * 64,
                "prior_authority_commit_receipt_id": str(uuid4()),
                "authority_commit_intent_id": str(uuid4()),
                "intended_mutation_digest": "b" * 64,
                "request_context_id": str(uuid4()),
                "authorization_snapshot_id": str(uuid4()),
                "authorization_snapshot_digest": "c" * 64,
                "action": "project.create",
                "resource": "project",
                "decision": "allow",
                "reason_code": "authorized",
                "policy_digest": "d" * 64,
                "sanitized_input_digest": "e" * 64,
                "signing_key_version_id": str(uuid4()),
                "previous_hash": "f" * 64,
                "receipt_hash": "1" * 64,
                "receipt_signature": "signed-receipt",
                "resulting_authority_state_root": "2" * 64,
            }
        )

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"
    assert tuple(exc_info.value.errors()[0]["loc"]) == ("resulting_authority_state_root",)


def test_authorization_snapshot_requires_requester_and_agent_authority_inputs() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuthorizationDecisionSnapshot.model_validate({})

    missing = {
        tuple(error["loc"]) for error in exc_info.value.errors() if error["type"] == "missing"
    }
    assert {
        ("workspace_id",),
        ("requester_id",),
        ("access_bundle_id",),
        ("agent_grant_id",),
        ("authority_commit_receipt_id",),
        ("signing_key_version_id",),
        ("snapshot_signature",),
    } <= missing


def test_revoked_signing_key_rejects_post_revocation_signature() -> None:
    now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    key = WorkspaceSigningKeyVersion(
        workspace_id=uuid4(),
        key_epoch=2,
        algorithm="ed25519",
        public_key="public-key-material",
        non_exportable_private_key_ref="keyring://workspace/signing/2",
        status=SigningKeyStatus.REVOKED,
        valid_from=now - timedelta(days=1),
        revoked_at=now,
        predecessor_digest="a" * 64,
        attestation_digest="b" * 64,
    )

    with pytest.raises(ValueError, match="signing_key_revoked_at_signing_time"):
        validate_signing_time(key, now + timedelta(seconds=1))


@pytest.mark.parametrize(
    ("close_anchor_digest", "key_disposition", "key_evidence_digest", "reason_code"),
    [
        (None, EpochKeyDisposition.DESTROYED, "a" * 64, "handoff_close_not_anchored"),
        (
            "b" * 64,
            EpochKeyDisposition.PENDING,
            None,
            "handoff_old_epoch_key_still_active",
        ),
    ],
)
def test_handoff_activation_requires_anchored_close_and_old_key_disposition(
    close_anchor_digest: str | None,
    key_disposition: EpochKeyDisposition,
    key_evidence_digest: str | None,
    reason_code: str,
) -> None:
    workspace_id = uuid4()
    close = AuthorityCloseCertificate(
        workspace_id=workspace_id,
        source_deployment_instance_id=uuid4(),
        authority_epoch=4,
        final_generation=19,
        final_state_root="c" * 64,
        anchored_close_receipt_digest=close_anchor_digest,
        epoch_key_disposition=key_disposition,
        epoch_key_disposition_evidence_digest=key_evidence_digest,
        closed_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
    )
    activation = AuthorityHandoffActivation(
        workspace_id=workspace_id,
        target_deployment_instance_id=uuid4(),
        authority_epoch=5,
        source_close_certificate_id=close.id,
        source_close_certificate_digest="d" * 64,
        authority_epoch_credential_id=uuid4(),
        exclusive_lease_or_local_anchor_receipt_digest="e" * 64,
        activated_at=datetime(2026, 7, 14, 12, 1, tzinfo=UTC),
    )

    with pytest.raises(AuthorityContractError) as exc_info:
        validate_handoff_activation(close, activation)

    assert exc_info.value.reason_code == reason_code
