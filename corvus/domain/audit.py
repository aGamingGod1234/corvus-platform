from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _now_utc() -> datetime:
    return datetime.now(UTC)


class SigningKeyStatus(StrEnum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    COMPROMISED = "compromised"


class WorkspaceSigningKeyVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    key_epoch: int = Field(ge=1)
    algorithm: str = Field(min_length=1, max_length=100)
    public_key: str = Field(min_length=1)
    non_exportable_private_key_ref: str = Field(min_length=1)
    status: SigningKeyStatus
    valid_from: datetime
    valid_until: datetime | None = None
    revoked_at: datetime | None = None
    compromise_effective_at: datetime | None = None
    predecessor_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attestation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=_now_utc)


def validate_signing_time(key: WorkspaceSigningKeyVersion, signing_time: datetime) -> None:
    if (
        key.status is SigningKeyStatus.REVOKED
        and key.revoked_at is not None
        and signing_time >= key.revoked_at
    ):
        raise ValueError("signing_key_revoked_at_signing_time")


class AuthorizationDecisionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    request_context_id: UUID
    deployment_instance_id: UUID
    authority_epoch_credential_id: UUID
    authority_generation: int = Field(ge=0)
    authority_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_commit_receipt_id: UUID
    authority_proof_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    membership_version_ids: tuple[UUID, ...]
    membership_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope_kind: Literal["workspace", "project", "channel", "thread", "conversation"]
    scope_id: UUID
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    audience_policy_snapshot_id: UUID
    audience_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    requester_id: UUID
    transport_principal_id: UUID
    access_bundle_id: UUID
    access_bundle_version_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_grant_id: UUID
    delegation_grant_ids: tuple[UUID, ...] = ()
    agent_delegation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_placement_id: UUID | None = None
    provider_connection_id: UUID | None = None
    credential_grant_id: UUID | None = None
    credential_version_id: UUID | None = None
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    autonomy_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_snapshot_ids: tuple[UUID, ...]
    budget_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    kill_switch_snapshot_ids: tuple[UUID, ...]
    kill_switch_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["allow", "deny"]
    reason_code: str = Field(min_length=1, max_length=200)
    canonical_inputs_json: dict[str, Any]
    source_record_version_map: dict[str, int]
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    signing_key_version_id: UUID
    snapshot_signature: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_now_utc)


class AuditReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    workspace_sequence: int = Field(ge=1)
    schema_version: int = Field(ge=1)
    prior_authority_epoch: int = Field(ge=1)
    prior_authority_generation: int = Field(ge=0)
    prior_authority_state_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_authority_commit_receipt_id: UUID
    authority_commit_intent_id: UUID
    intended_mutation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_context_id: UUID
    authorization_snapshot_id: UUID
    authorization_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: str = Field(min_length=1, max_length=200)
    resource: str = Field(min_length=1, max_length=500)
    decision: Literal["allow", "deny"]
    reason_code: str = Field(min_length=1, max_length=200)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sanitized_input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    effect_payload_version_ids: tuple[UUID, ...] = ()
    effect_payload_commitment_digests: tuple[str, ...] = ()
    effect_attempt_ids: tuple[UUID, ...] = ()
    cost_json: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: tuple[UUID, ...] = ()
    signing_key_version_id: UUID
    previous_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_signature: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_now_utc)
