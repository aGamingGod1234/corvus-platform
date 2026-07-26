from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from corvus.security import canonical_json_bytes

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_GENESIS_EVENT_DIGEST = "0" * 64


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _execution_error(reason_code: str) -> None:
    raise PydanticCustomError(
        "execution_contract_error",
        "reason_code={reason_code}",
        {"reason_code": reason_code},
    )


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        _execution_error("execution_timestamp_must_be_timezone_aware")
    return value


def _compute_contract_digest(
    contract_name: str,
    value: BaseModel | Mapping[str, object],
) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="python", exclude={"canonical_digest"})
    else:
        payload = dict(value)
        payload.pop("canonical_digest", None)
    return hashlib.sha256(
        canonical_json_bytes({"contract": contract_name, "payload": payload})
    ).hexdigest()


class ExecutionKind(StrEnum):
    LOCAL_RUNNER = "local_runner"
    CLOUD_WORKER = "cloud_worker"
    CONNECTOR = "connector"


class ExecutionStatus(StrEnum):
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    REVOKED = "revoked"


class ExecutionRunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStepState(StrEnum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionNextTransition(StrEnum):
    DISPATCH = "dispatch"
    RESUME = "resume"
    RETRY = "retry"
    WAIT = "wait"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"


class EffectIntentKind(StrEnum):
    PROVIDER = "provider"
    CONNECTOR = "connector"
    FILESYSTEM_APPLY = "filesystem_apply"
    FILESYSTEM_UNDO = "filesystem_undo"


class EffectIntentState(StrEnum):
    PENDING = "pending"
    PERMITTED = "permitted"
    DISPATCHING = "dispatching"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    CANCELLED = "cancelled"


class EffectPermitState(StrEnum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    CANCELLED = "cancelled"
    CONSUMED = "consumed"


class EffectReceiptOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    OUTCOME_UNKNOWN = "outcome_unknown"


class ExecutionPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    kind: ExecutionKind
    runner_id: UUID | None = None
    connector_id: UUID | None = None
    sandbox_profile: str = Field(min_length=1)
    data_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ExecutionStatus = ExecutionStatus.ACTIVE
    created_at: datetime = Field(default_factory=_now_utc)

    @model_validator(mode="after")
    def validate_discriminator_fields(self) -> ExecutionPlacement:
        if self.kind is ExecutionKind.CONNECTOR:
            if self.connector_id is None or self.runner_id is not None:
                raise PydanticCustomError(
                    "invalid_execution_identity",
                    "reason_code={reason_code}",
                    {"reason_code": "connector_requires_only_connector_id"},
                )
        elif self.runner_id is None or self.connector_id is not None:
            raise PydanticCustomError(
                "invalid_execution_identity",
                "reason_code={reason_code}",
                {"reason_code": "runner_placement_requires_only_runner_id"},
            )
        return self


class _ExecutionContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


class ExecutionRun(_ExecutionContractModel):
    id: UUID
    tenant_id: UUID
    state: ExecutionRunState
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    canonical_digest: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_contract(self) -> ExecutionRun:
        if self.updated_at < self.created_at:
            _execution_error("execution_run_updated_before_creation")
        if self.canonical_digest != compute_execution_run_digest(self):
            _execution_error("execution_run_digest_mismatch")
        return self


def compute_execution_run_digest(value: ExecutionRun | Mapping[str, object]) -> str:
    return _compute_contract_digest("execution_run", value)


class ExecutionStep(_ExecutionContractModel):
    id: UUID
    tenant_id: UUID
    run_id: UUID
    state: ExecutionStepState
    fence: int = Field(ge=1)
    version: int = Field(ge=1)
    retry_count: int = Field(ge=0)
    attempt_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    canonical_digest: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_contract(self) -> ExecutionStep:
        if self.updated_at < self.created_at:
            _execution_error("execution_step_updated_before_creation")
        if self.retry_count > self.attempt_count:
            _execution_error("execution_step_retry_count_exceeds_attempt_count")
        if self.canonical_digest != compute_execution_step_digest(self):
            _execution_error("execution_step_digest_mismatch")
        return self


def compute_execution_step_digest(value: ExecutionStep | Mapping[str, object]) -> str:
    return _compute_contract_digest("execution_step", value)


class ExecutionCheckpoint(_ExecutionContractModel):
    id: UUID
    tenant_id: UUID
    run_id: UUID
    step_id: UUID
    run_state: ExecutionRunState
    step_state: ExecutionStepState
    step_fence: int = Field(ge=1)
    step_version: int = Field(ge=1)
    checkpoint_version: int = Field(ge=1)
    completed_dependency_step_ids: tuple[UUID, ...] = ()
    output_ref_ids: tuple[UUID, ...] = ()
    artifact_ref_ids: tuple[UUID, ...] = ()
    retry_count: int = Field(ge=0)
    attempt_count: int = Field(ge=0)
    last_accepted_event_sequence: int = Field(ge=0)
    last_accepted_event_digest: str = Field(pattern=_SHA256_PATTERN)
    next_transition: ExecutionNextTransition
    created_at: datetime
    canonical_digest: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_contract(self) -> ExecutionCheckpoint:
        reference_groups = (
            self.completed_dependency_step_ids,
            self.output_ref_ids,
            self.artifact_ref_ids,
        )
        if any(len(values) != len(set(values)) for values in reference_groups):
            _execution_error("execution_checkpoint_duplicate_reference")
        if self.step_id in self.completed_dependency_step_ids:
            _execution_error("execution_checkpoint_self_dependency")
        if self.retry_count > self.attempt_count:
            _execution_error("execution_checkpoint_retry_count_exceeds_attempt_count")
        if (
            self.last_accepted_event_sequence == 0
            and self.last_accepted_event_digest != _GENESIS_EVENT_DIGEST
        ):
            _execution_error("execution_checkpoint_genesis_event_digest_mismatch")
        if self.canonical_digest != compute_execution_checkpoint_digest(self):
            _execution_error("execution_checkpoint_digest_mismatch")
        return self


def compute_execution_checkpoint_digest(
    value: ExecutionCheckpoint | Mapping[str, object],
) -> str:
    return _compute_contract_digest("execution_checkpoint", value)


class EffectIntent(_ExecutionContractModel):
    id: UUID
    tenant_id: UUID
    run_id: UUID
    step_id: UUID
    step_fence: int = Field(ge=1)
    step_version: int = Field(ge=1)
    kind: EffectIntentKind
    target_ref_id: UUID
    request_digest: str = Field(pattern=_SHA256_PATTERN)
    semantic_idempotency_key: str = Field(min_length=1, max_length=512)
    state: EffectIntentState
    created_at: datetime
    canonical_digest: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @field_validator("semantic_idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            _execution_error("effect_intent_idempotency_key_blank")
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> EffectIntent:
        if self.canonical_digest != compute_effect_intent_digest(self):
            _execution_error("effect_intent_digest_mismatch")
        return self


def compute_effect_intent_digest(value: EffectIntent | Mapping[str, object]) -> str:
    return _compute_contract_digest("effect_intent", value)


class EffectPermit(_ExecutionContractModel):
    id: UUID
    tenant_id: UUID
    run_id: UUID
    step_id: UUID
    intent_id: UUID
    intent_digest: str = Field(pattern=_SHA256_PATTERN)
    step_fence: int = Field(ge=1)
    step_version: int = Field(ge=1)
    authorization_proof_id: UUID
    authorization_proof_digest: str = Field(pattern=_SHA256_PATTERN)
    autonomy_proof_id: UUID
    autonomy_proof_digest: str = Field(pattern=_SHA256_PATTERN)
    credential_proof_id: UUID
    credential_proof_digest: str = Field(pattern=_SHA256_PATTERN)
    budget_proof_id: UUID
    budget_proof_digest: str = Field(pattern=_SHA256_PATTERN)
    kill_switch_proof_id: UUID
    kill_switch_proof_digest: str = Field(pattern=_SHA256_PATTERN)
    state: EffectPermitState
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_contract(self) -> EffectPermit:
        if self.expires_at <= self.issued_at:
            _execution_error("effect_permit_expiry_invalid")
        if self.canonical_digest != compute_effect_permit_digest(self):
            _execution_error("effect_permit_digest_mismatch")
        return self


def compute_effect_permit_digest(value: EffectPermit | Mapping[str, object]) -> str:
    return _compute_contract_digest("effect_permit", value)


class EffectReceipt(_ExecutionContractModel):
    id: UUID
    tenant_id: UUID
    run_id: UUID
    step_id: UUID
    step_fence: int = Field(ge=1)
    intent_id: UUID
    intent_digest: str = Field(pattern=_SHA256_PATTERN)
    permit_id: UUID
    permit_digest: str = Field(pattern=_SHA256_PATTERN)
    outcome: EffectReceiptOutcome
    sanitized_result_ref_id: UUID | None = None
    sanitized_result_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    recorded_at: datetime
    canonical_digest: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_contract(self) -> EffectReceipt:
        if (self.sanitized_result_ref_id is None) != (self.sanitized_result_digest is None):
            _execution_error("effect_receipt_result_reference_incomplete")
        if (
            self.outcome is EffectReceiptOutcome.OUTCOME_UNKNOWN
            and self.sanitized_result_ref_id is not None
        ):
            _execution_error("effect_receipt_unknown_outcome_has_result")
        if self.canonical_digest != compute_effect_receipt_digest(self):
            _execution_error("effect_receipt_digest_mismatch")
        return self


def compute_effect_receipt_digest(value: EffectReceipt | Mapping[str, object]) -> str:
    return _compute_contract_digest("effect_receipt", value)
