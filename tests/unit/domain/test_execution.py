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
WORKSPACE_ID = UUID("00000000-0000-0000-0000-000000000001")
RUN_ID = UUID("00000000-0000-0000-0000-000000000002")
STEP_ID = UUID("00000000-0000-0000-0000-000000000003")


def _signed(
    payload: dict[str, object],
    digest: Callable[[dict[str, object]], str],
) -> dict[str, object]:
    return {**payload, "canonical_digest": digest(payload)}


def test_execution_binding_authenticates_immutable_request_and_rejects_tampering() -> None:
    payload: dict[str, object] = {
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "immutable_request_digest": "a" * 64,
        "created_at": NOW,
    }
    binding = execution.AgentRunExecutionBinding(
        **_signed(payload, execution.compute_agent_run_execution_binding_digest)  # type: ignore[arg-type]
    )

    assert binding.immutable_request_digest == "a" * 64
    with pytest.raises(
        ValidationError,
        match="agent_run_execution_binding_digest_mismatch",
    ):
        execution.AgentRunExecutionBinding(
            **{
                **binding.model_dump(mode="python"),
                "immutable_request_digest": "b" * 64,
            }
        )
    with pytest.raises(
        ValidationError,
        match="execution_timestamp_must_be_timezone_aware",
    ):
        execution.AgentRunExecutionBinding(
            **{
                **binding.model_dump(mode="python"),
                "created_at": datetime(2026, 7, 26, 12, 0),
            }
        )


def test_execution_run_and_step_bind_workspace_run_and_fence() -> None:
    run_payload: dict[str, object] = {
        "id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
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
        "workspace_id": WORKSPACE_ID,
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

    assert (step.workspace_id, step.run_id, step.fence) == (
        run.workspace_id,
        run.id,
        7,
    )

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
        "workspace_id": WORKSPACE_ID,
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
        "workspace_id": WORKSPACE_ID,
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
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "step_id": STEP_ID,
        "intent_id": intent.id,
        "intent_digest": intent.canonical_digest,
        "step_fence": intent.step_fence,
        "step_version": intent.step_version,
        "authorization_proof_id": UUID("00000000-0000-0000-0000-000000000023"),
        "authorization_proof_digest": "c" * 64,
        "autonomy_grant_id": UUID("00000000-0000-0000-0000-000000000024"),
        "autonomy_grant_digest": "d" * 64,
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
        "workspace_id": WORKSPACE_ID,
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
                "workspace_id": WORKSPACE_ID,
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
                "workspace_id": WORKSPACE_ID,
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
                "workspace_id": WORKSPACE_ID,
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
                "workspace_id": WORKSPACE_ID,
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
                "workspace_id": WORKSPACE_ID,
                "run_id": RUN_ID,
                "step_id": STEP_ID,
                "intent_id": intent.id,
                "intent_digest": intent.canonical_digest,
                "step_fence": 1,
                "step_version": 1,
                "authorization_proof_id": UUID("00000000-0000-0000-0000-000000000044"),
                "authorization_proof_digest": "b" * 64,
                "autonomy_grant_id": UUID("00000000-0000-0000-0000-000000000045"),
                "autonomy_grant_digest": "c" * 64,
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
                "workspace_id": WORKSPACE_ID,
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
            contract.workspace_id = UUID("00000000-0000-0000-0000-000000000099")

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


def test_checkpoint_rejects_state_transition_contradictions() -> None:
    checkpoint = _contract_examples()[2][0]
    payload = checkpoint.model_dump(mode="python", exclude={"canonical_digest"})

    completed_payload = {
        **payload,
        "run_state": execution.ExecutionRunState.COMPLETED,
        "step_state": execution.ExecutionStepState.COMPLETED,
        "next_transition": execution.ExecutionNextTransition.COMPLETE,
    }
    completed = execution.ExecutionCheckpoint(
        **_signed(completed_payload, execution.compute_execution_checkpoint_digest)  # type: ignore[arg-type]
    )
    assert completed.next_transition is execution.ExecutionNextTransition.COMPLETE

    for run_state, step_state, next_transition in (
        (
            execution.ExecutionRunState.COMPLETED,
            execution.ExecutionStepState.PAUSED,
            execution.ExecutionNextTransition.RESUME,
        ),
        (
            execution.ExecutionRunState.FAILED,
            execution.ExecutionStepState.FAILED,
            execution.ExecutionNextTransition.RETRY,
        ),
        (
            execution.ExecutionRunState.RUNNING,
            execution.ExecutionStepState.RUNNING,
            execution.ExecutionNextTransition.DISPATCH,
        ),
    ):
        contradictory = {
            **payload,
            "run_state": run_state,
            "step_state": step_state,
            "next_transition": next_transition,
        }
        with pytest.raises(
            ValidationError,
            match="execution_checkpoint_state_transition_invalid",
        ):
            execution.ExecutionCheckpoint(
                **_signed(
                    contradictory,
                    execution.compute_execution_checkpoint_digest,
                )  # type: ignore[arg-type]
            )


def test_checkpoint_allows_completed_step_while_multi_step_run_continues() -> None:
    checkpoint = _contract_examples()[2][0]
    payload = checkpoint.model_dump(mode="python", exclude={"canonical_digest"})
    continuing_payload = {
        **payload,
        "run_state": execution.ExecutionRunState.RUNNING,
        "step_state": execution.ExecutionStepState.COMPLETED,
        "next_transition": execution.ExecutionNextTransition.WAIT,
    }

    continuing = execution.ExecutionCheckpoint(
        **_signed(
            continuing_payload,
            execution.compute_execution_checkpoint_digest,
        )  # type: ignore[arg-type]
    )
    assert continuing.step_state is execution.ExecutionStepState.COMPLETED

    terminal_contradiction = {
        **continuing_payload,
        "run_state": execution.ExecutionRunState.COMPLETED,
    }
    with pytest.raises(
        ValidationError,
        match="execution_checkpoint_state_transition_invalid",
    ):
        execution.ExecutionCheckpoint(
            **_signed(
                terminal_contradiction,
                execution.compute_execution_checkpoint_digest,
            )  # type: ignore[arg-type]
        )


def test_mapping_digest_helpers_use_pydantic_datetime_normalization() -> None:
    digest_helpers = (
        execution.compute_execution_run_digest,
        execution.compute_execution_step_digest,
        execution.compute_execution_checkpoint_digest,
        execution.compute_effect_intent_digest,
        execution.compute_effect_permit_digest,
        execution.compute_effect_receipt_digest,
    )

    for (contract, _), digest_helper in zip(
        _contract_examples(),
        digest_helpers,
        strict=True,
    ):
        mapping = contract.model_dump(mode="python", exclude={"canonical_digest"})
        for field, value in tuple(mapping.items()):
            if isinstance(value, datetime):
                mapping[field] = value.isoformat().replace("+00:00", "Z")

        digest = digest_helper(mapping)

        assert digest == contract.canonical_digest
        rebuilt = contract.__class__.model_validate({**mapping, "canonical_digest": digest})
        assert rebuilt.canonical_digest == contract.canonical_digest


def test_checkpoint_event_sequence_and_genesis_digest_are_biconditional() -> None:
    checkpoint = _contract_examples()[2][0]
    payload = checkpoint.model_dump(mode="python", exclude={"canonical_digest"})

    for sequence, event_digest in ((0, "a" * 64), (1, "0" * 64)):
        contradictory = {
            **payload,
            "last_accepted_event_sequence": sequence,
            "last_accepted_event_digest": event_digest,
        }
        with pytest.raises(
            ValidationError,
            match="execution_checkpoint_event_sentinel_mismatch",
        ):
            execution.ExecutionCheckpoint(
                **_signed(
                    contradictory,
                    execution.compute_execution_checkpoint_digest,
                )  # type: ignore[arg-type]
            )


def test_security_sensitive_integer_fields_reject_booleans() -> None:
    digest_helpers = (
        execution.compute_execution_run_digest,
        execution.compute_execution_step_digest,
        execution.compute_execution_checkpoint_digest,
        execution.compute_effect_intent_digest,
        execution.compute_effect_permit_digest,
        execution.compute_effect_receipt_digest,
    )
    integer_fields = (
        ("version",),
        ("fence", "version", "retry_count", "attempt_count"),
        (
            "step_fence",
            "step_version",
            "checkpoint_version",
            "retry_count",
            "attempt_count",
            "last_accepted_event_sequence",
        ),
        ("step_fence", "step_version"),
        ("step_fence", "step_version"),
        ("step_fence",),
    )

    for (contract, _), digest_helper, fields in zip(
        _contract_examples(),
        digest_helpers,
        integer_fields,
        strict=True,
    ):
        payload = contract.model_dump(mode="python", exclude={"canonical_digest"})
        for field in fields:
            boolean_payload = {**payload, field: True}
            with pytest.raises(ValidationError, match="int_type"):
                contract.__class__(**_signed(boolean_payload, digest_helper))


def test_effect_permit_uses_autonomy_grant_references_only() -> None:
    permit = _contract_examples()[4][0]
    payload = permit.model_dump(mode="python", exclude={"canonical_digest"})
    autonomy_grant_id = payload["autonomy_grant_id"]
    autonomy_grant_digest = payload["autonomy_grant_digest"]

    aligned = execution.EffectPermit(
        **_signed(payload, execution.compute_effect_permit_digest)  # type: ignore[arg-type]
    )
    assert (aligned.autonomy_grant_id, aligned.autonomy_grant_digest) == (
        autonomy_grant_id,
        autonomy_grant_digest,
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        execution.EffectPermit(
            **{
                **aligned.model_dump(mode="python"),
                "autonomy_proof_id": autonomy_grant_id,
            }
        )


def test_execution_contracts_use_workspace_id_and_reject_legacy_tenant_id() -> None:
    payload: dict[str, object] = {
        "id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "state": execution.ExecutionRunState.RUNNING,
        "version": 1,
        "created_at": NOW,
        "updated_at": LATER,
    }
    run = execution.ExecutionRun(
        **_signed(payload, execution.compute_execution_run_digest)  # type: ignore[arg-type]
    )
    assert run.workspace_id == WORKSPACE_ID

    with pytest.raises(ValidationError, match="extra_forbidden"):
        execution.ExecutionRun(**{**run.model_dump(mode="python"), "tenant_id": WORKSPACE_ID})
