from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from corvus.domain import execution

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 26, 12, 5, tzinfo=UTC)
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
RUN_ID = UUID("00000000-0000-0000-0000-000000000002")
STEP_ID = UUID("00000000-0000-0000-0000-000000000003")


def _signed(
    payload: dict[str, object],
    digest: Callable[[dict[str, object]], str],
) -> dict[str, object]:
    return {**payload, "canonical_digest": digest(payload)}


def test_execution_run_and_step_bind_tenant_run_and_fence() -> None:
    run_payload: dict[str, object] = {
        "id": RUN_ID,
        "tenant_id": TENANT_ID,
        "state": execution.ExecutionRunState.RUNNING,
        "version": 4,
        "created_at": NOW,
        "updated_at": LATER,
    }
    run = execution.ExecutionRun(
        **_signed(run_payload, execution.compute_execution_run_digest)  # type: ignore[arg-type]
    )
    step_payload: dict[str, object] = {
        "id": STEP_ID,
        "tenant_id": TENANT_ID,
        "run_id": run.id,
        "state": execution.ExecutionStepState.RUNNING,
        "fence": 7,
        "version": 3,
        "retry_count": 1,
        "attempt_count": 2,
        "created_at": NOW,
        "updated_at": LATER,
    }
    step = execution.ExecutionStep(
        **_signed(step_payload, execution.compute_execution_step_digest)  # type: ignore[arg-type]
    )

    assert (step.tenant_id, step.run_id, step.fence) == (run.tenant_id, run.id, 7)

    with pytest.raises(ValidationError, match="execution_step_digest_mismatch"):
        execution.ExecutionStep(
            **{
                **step.model_dump(mode="python"),
                "run_id": UUID("00000000-0000-0000-0000-000000000099"),
            }
        )


def test_checkpoint_is_provider_neutral_and_rejects_tampering() -> None:
    payload: dict[str, object] = {
        "id": UUID("00000000-0000-0000-0000-000000000004"),
        "tenant_id": TENANT_ID,
        "run_id": RUN_ID,
        "step_id": STEP_ID,
        "run_state": execution.ExecutionRunState.RUNNING,
        "step_state": execution.ExecutionStepState.PAUSED,
        "step_fence": 7,
        "step_version": 3,
        "checkpoint_version": 2,
        "completed_dependency_step_ids": (UUID("00000000-0000-0000-0000-000000000010"),),
        "output_ref_ids": (UUID("00000000-0000-0000-0000-000000000011"),),
        "artifact_ref_ids": (UUID("00000000-0000-0000-0000-000000000012"),),
        "retry_count": 1,
        "attempt_count": 2,
        "last_accepted_event_sequence": 8,
        "last_accepted_event_digest": "a" * 64,
        "next_transition": execution.ExecutionNextTransition.RESUME,
        "created_at": NOW,
    }
    checkpoint = execution.ExecutionCheckpoint(
        **_signed(payload, execution.compute_execution_checkpoint_digest)  # type: ignore[arg-type]
    )

    assert checkpoint.completed_dependency_step_ids == (
        UUID("00000000-0000-0000-0000-000000000010"),
    )

    for forbidden in ("provider_session_ref", "prompt"):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            execution.ExecutionCheckpoint(
                **{**checkpoint.model_dump(mode="python"), forbidden: "not resumable state"}
            )

    with pytest.raises(ValidationError, match="execution_checkpoint_digest_mismatch"):
        execution.ExecutionCheckpoint(**{**checkpoint.model_dump(mode="python"), "step_fence": 8})


def test_permit_binds_intent_proofs_fence_version_and_expiry() -> None:
    intent_id = UUID("00000000-0000-0000-0000-000000000020")
    intent_payload: dict[str, object] = {
        "id": intent_id,
        "tenant_id": TENANT_ID,
        "run_id": RUN_ID,
        "step_id": STEP_ID,
        "step_fence": 7,
        "step_version": 3,
        "kind": execution.EffectIntentKind.CONNECTOR,
        "target_ref_id": UUID("00000000-0000-0000-0000-000000000021"),
        "request_digest": "b" * 64,
        "semantic_idempotency_key": "send-approved-message-1",
        "state": execution.EffectIntentState.PENDING,
        "created_at": NOW,
    }
    intent = execution.EffectIntent(
        **_signed(intent_payload, execution.compute_effect_intent_digest)  # type: ignore[arg-type]
    )
    permit_payload: dict[str, object] = {
        "id": UUID("00000000-0000-0000-0000-000000000022"),
        "tenant_id": TENANT_ID,
        "run_id": RUN_ID,
        "step_id": STEP_ID,
        "intent_id": intent.id,
        "intent_digest": intent.canonical_digest,
        "step_fence": intent.step_fence,
        "step_version": intent.step_version,
        "authorization_proof_id": UUID("00000000-0000-0000-0000-000000000023"),
        "authorization_proof_digest": "c" * 64,
        "autonomy_proof_id": UUID("00000000-0000-0000-0000-000000000024"),
        "autonomy_proof_digest": "d" * 64,
        "credential_proof_id": UUID("00000000-0000-0000-0000-000000000025"),
        "credential_proof_digest": "e" * 64,
        "budget_proof_id": UUID("00000000-0000-0000-0000-000000000026"),
        "budget_proof_digest": "f" * 64,
        "kill_switch_proof_id": UUID("00000000-0000-0000-0000-000000000027"),
        "kill_switch_proof_digest": "1" * 64,
        "state": execution.EffectPermitState.AVAILABLE,
        "issued_at": NOW,
        "expires_at": LATER,
    }
    permit = execution.EffectPermit(
        **_signed(permit_payload, execution.compute_effect_permit_digest)  # type: ignore[arg-type]
    )

    assert (permit.intent_id, permit.step_fence, permit.step_version) == (
        intent.id,
        intent.step_fence,
        intent.step_version,
    )

    for field, value in (
        ("intent_digest", "9" * 64),
        ("step_fence", 8),
        ("authorization_proof_digest", "8" * 64),
    ):
        with pytest.raises(ValidationError, match="effect_permit_digest_mismatch"):
            execution.EffectPermit(**{**permit.model_dump(mode="python"), field: value})

    expired_payload = {**permit_payload, "expires_at": NOW}
    with pytest.raises(ValidationError, match="effect_permit_expiry_invalid"):
        execution.EffectPermit(
            **_signed(expired_payload, execution.compute_effect_permit_digest)  # type: ignore[arg-type]
        )


def test_receipt_uses_explicit_outcomes_and_rejects_tampering() -> None:
    payload: dict[str, object] = {
        "id": UUID("00000000-0000-0000-0000-000000000030"),
        "tenant_id": TENANT_ID,
        "run_id": RUN_ID,
        "step_id": STEP_ID,
        "step_fence": 7,
        "intent_id": UUID("00000000-0000-0000-0000-000000000020"),
        "intent_digest": "2" * 64,
        "permit_id": UUID("00000000-0000-0000-0000-000000000022"),
        "permit_digest": "3" * 64,
        "outcome": execution.EffectReceiptOutcome.SUCCESS,
        "sanitized_result_ref_id": UUID("00000000-0000-0000-0000-000000000031"),
        "sanitized_result_digest": "4" * 64,
        "recorded_at": NOW,
    }
    receipt = execution.EffectReceipt(
        **_signed(payload, execution.compute_effect_receipt_digest)  # type: ignore[arg-type]
    )

    observed_outcomes = {receipt.outcome}
    for outcome in (
        execution.EffectReceiptOutcome.FAILURE,
        execution.EffectReceiptOutcome.OUTCOME_UNKNOWN,
    ):
        outcome_payload = {
            **payload,
            "outcome": outcome,
            "sanitized_result_ref_id": None,
            "sanitized_result_digest": None,
        }
        observed_outcomes.add(
            execution.EffectReceipt(
                **_signed(outcome_payload, execution.compute_effect_receipt_digest)  # type: ignore[arg-type]
            ).outcome
        )
    assert observed_outcomes == set(execution.EffectReceiptOutcome)

    with pytest.raises(ValidationError, match="effect_receipt_digest_mismatch"):
        execution.EffectReceipt(**{**receipt.model_dump(mode="python"), "permit_digest": "5" * 64})

    unknown_with_result = {
        **payload,
        "outcome": execution.EffectReceiptOutcome.OUTCOME_UNKNOWN,
    }
    with pytest.raises(ValidationError, match="effect_receipt_unknown_outcome_has_result"):
        execution.EffectReceipt(
            **_signed(unknown_with_result, execution.compute_effect_receipt_digest)  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        execution.EffectReceipt(
            **{**receipt.model_dump(mode="python"), "result": {"token": "secret"}}
        )


def _contract_examples() -> list[tuple[Any, str]]:
    run = execution.ExecutionRun(
        **_signed(
            {
                "id": RUN_ID,
                "tenant_id": TENANT_ID,
                "state": execution.ExecutionRunState.RUNNING,
                "version": 1,
                "created_at": NOW,
                "updated_at": LATER,
            },
            execution.compute_execution_run_digest,
        )  # type: ignore[arg-type]
    )
    step = execution.ExecutionStep(
        **_signed(
            {
                "id": STEP_ID,
                "tenant_id": TENANT_ID,
                "run_id": RUN_ID,
                "state": execution.ExecutionStepState.RUNNING,
                "fence": 1,
                "version": 1,
                "retry_count": 0,
                "attempt_count": 1,
                "created_at": NOW,
                "updated_at": LATER,
            },
            execution.compute_execution_step_digest,
        )  # type: ignore[arg-type]
    )
    checkpoint = execution.ExecutionCheckpoint(
        **_signed(
            {
                "id": UUID("00000000-0000-0000-0000-000000000040"),
                "tenant_id": TENANT_ID,
                "run_id": RUN_ID,
                "step_id": STEP_ID,
                "run_state": execution.ExecutionRunState.RUNNING,
                "step_state": execution.ExecutionStepState.PAUSED,
                "step_fence": 1,
                "step_version": 1,
                "checkpoint_version": 1,
                "completed_dependency_step_ids": (),
                "output_ref_ids": (),
                "artifact_ref_ids": (),
                "retry_count": 0,
                "attempt_count": 1,
                "last_accepted_event_sequence": 0,
                "last_accepted_event_digest": "0" * 64,
                "next_transition": execution.ExecutionNextTransition.RESUME,
                "created_at": NOW,
            },
            execution.compute_execution_checkpoint_digest,
        )  # type: ignore[arg-type]
    )
    intent = execution.EffectIntent(
        **_signed(
            {
                "id": UUID("00000000-0000-0000-0000-000000000041"),
                "tenant_id": TENANT_ID,
                "run_id": RUN_ID,
                "step_id": STEP_ID,
                "step_fence": 1,
                "step_version": 1,
                "kind": execution.EffectIntentKind.CONNECTOR,
                "target_ref_id": UUID("00000000-0000-0000-0000-000000000042"),
                "request_digest": "a" * 64,
                "semantic_idempotency_key": "example-effect",
                "state": execution.EffectIntentState.PENDING,
                "created_at": NOW,
            },
            execution.compute_effect_intent_digest,
        )  # type: ignore[arg-type]
    )
    permit = execution.EffectPermit(
        **_signed(
            {
                "id": UUID("00000000-0000-0000-0000-000000000043"),
                "tenant_id": TENANT_ID,
                "run_id": RUN_ID,
                "step_id": STEP_ID,
                "intent_id": intent.id,
                "intent_digest": intent.canonical_digest,
                "step_fence": 1,
                "step_version": 1,
                "authorization_proof_id": UUID("00000000-0000-0000-0000-000000000044"),
                "authorization_proof_digest": "b" * 64,
                "autonomy_proof_id": UUID("00000000-0000-0000-0000-000000000045"),
                "autonomy_proof_digest": "c" * 64,
                "credential_proof_id": UUID("00000000-0000-0000-0000-000000000046"),
                "credential_proof_digest": "d" * 64,
                "budget_proof_id": UUID("00000000-0000-0000-0000-000000000047"),
                "budget_proof_digest": "e" * 64,
                "kill_switch_proof_id": UUID("00000000-0000-0000-0000-000000000048"),
                "kill_switch_proof_digest": "f" * 64,
                "state": execution.EffectPermitState.AVAILABLE,
                "issued_at": NOW,
                "expires_at": LATER,
            },
            execution.compute_effect_permit_digest,
        )  # type: ignore[arg-type]
    )
    receipt = execution.EffectReceipt(
        **_signed(
            {
                "id": UUID("00000000-0000-0000-0000-000000000049"),
                "tenant_id": TENANT_ID,
                "run_id": RUN_ID,
                "step_id": STEP_ID,
                "step_fence": 1,
                "intent_id": intent.id,
                "intent_digest": intent.canonical_digest,
                "permit_id": permit.id,
                "permit_digest": permit.canonical_digest,
                "outcome": execution.EffectReceiptOutcome.SUCCESS,
                "sanitized_result_ref_id": None,
                "sanitized_result_digest": None,
                "recorded_at": NOW,
            },
            execution.compute_effect_receipt_digest,
        )  # type: ignore[arg-type]
    )
    return [
        (run, "created_at"),
        (step, "created_at"),
        (checkpoint, "created_at"),
        (intent, "created_at"),
        (permit, "issued_at"),
        (receipt, "recorded_at"),
    ]


def test_execution_contract_models_are_frozen_strict_and_timezone_aware() -> None:
    for contract, timestamp_field in _contract_examples():
        with pytest.raises(ValidationError, match="frozen_instance"):
            contract.tenant_id = UUID("00000000-0000-0000-0000-000000000099")

        with pytest.raises(ValidationError, match="extra_forbidden"):
            contract.__class__.model_validate(
                {**contract.model_dump(mode="python"), "unexpected_payload": "blocked"}
            )

        with pytest.raises(
            ValidationError,
            match="execution_timestamp_must_be_timezone_aware",
        ):
            contract.__class__.model_validate(
                {
                    **contract.model_dump(mode="python"),
                    timestamp_field: datetime(2026, 7, 26, 12, 0),
                }
            )
