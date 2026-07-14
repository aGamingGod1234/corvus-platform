from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from pydantic import JsonValue

from corvus.domain.agent_runtime import (
    GENESIS_EVENT_DIGEST,
    AgentCapabilities,
    AgentRunEvent,
    AgentRunEventType,
    AgentRunHandle,
    AgentRunRequest,
    AgentRunState,
    CancellationResult,
    ProviderBinding,
    ProviderStatus,
    compute_agent_run_event_digest,
)

_SIMULATED_HANDLE_NAMESPACE = UUID("895c0f76-81a2-4f35-bd94-df91f86d266e")
_TERMINAL_EVENT_STATES = {
    AgentRunEventType.COMPLETED: AgentRunState.COMPLETED,
    AgentRunEventType.FAILED: AgentRunState.FAILED,
    AgentRunEventType.CANCELLED: AgentRunState.CANCELLED,
}


class AgentRuntimeError(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class SimulatedEventTemplate:
    event_type: AgentRunEventType
    redacted_payload: Mapping[str, JsonValue]
    provider_event_id: str | None = None


@dataclass
class _RunRecord:
    handle: AgentRunHandle
    events: list[AgentRunEvent]
    cancellation_result: CancellationResult | None = None


class SimulatedAgentRuntime:
    def __init__(
        self,
        *,
        bindings: tuple[ProviderBinding, ...],
        event_templates: Mapping[UUID, tuple[SimulatedEventTemplate, ...]],
    ) -> None:
        if len({binding.id for binding in bindings}) != len(bindings):
            raise AgentRuntimeError(
                "duplicate_provider_binding",
                "provider binding identities must be unique",
            )
        self._bindings = {
            binding.id: binding for binding in sorted(bindings, key=lambda item: str(item.id))
        }
        unknown_template_ids = set(event_templates) - self._bindings.keys()
        if unknown_template_ids:
            raise AgentRuntimeError(
                "unknown_event_template_binding",
                "event template references an unknown provider binding",
            )
        self._event_templates = {
            binding_id: tuple(self._snapshot_template(template) for template in templates)
            for binding_id, templates in event_templates.items()
        }
        self._runs: dict[UUID, _RunRecord] = {}

    def discover(self) -> tuple[ProviderBinding, ...]:
        return tuple(self._bindings.values())

    def capabilities(self, binding: ProviderBinding) -> AgentCapabilities:
        return self._known_binding(binding).capabilities

    def health(self, binding: ProviderBinding) -> ProviderStatus:
        return self._known_binding(binding).status

    async def start(self, request: AgentRunRequest) -> AgentRunHandle:
        binding = self._binding_for_start(request)
        handle_id = uuid5(
            _SIMULATED_HANDLE_NAMESPACE,
            f"{request.run_id}:{request.provider_binding_id}:{request.idempotency_key}",
        )
        existing = self._runs.get(handle_id)
        if existing is not None:
            return existing.handle

        events, state = self._materialize_events(
            request=request,
            handle_id=handle_id,
            binding=binding,
        )
        handle = AgentRunHandle(
            id=handle_id,
            run_id=request.run_id,
            provider_binding_id=binding.id,
            created_at=binding.health_checked_at,
            provider_session_ref=f"simulated-session:{handle_id}",
            state=state,
        )
        self._runs[handle.id] = _RunRecord(handle=handle, events=events)
        return handle

    async def events(
        self,
        handle: AgentRunHandle,
        after_sequence: int = 0,
    ) -> AsyncIterator[AgentRunEvent]:
        if after_sequence < 0:
            raise AgentRuntimeError(
                "invalid_event_sequence_cursor",
                "event sequence cursor cannot be negative",
            )
        record = self._known_record(handle)
        for event in tuple(record.events):
            if event.sequence > after_sequence:
                yield event

    async def cancel(
        self,
        handle: AgentRunHandle,
        current_kill_switch_proof_id: UUID,
    ) -> CancellationResult:
        if not isinstance(current_kill_switch_proof_id, UUID):
            raise AgentRuntimeError(
                "current_kill_switch_proof_required",
                "cancellation requires a current kill-switch proof reference",
            )
        record = self._known_record(handle)
        if record.cancellation_result is not None:
            return record.cancellation_result

        if record.handle.state is not AgentRunState.RUNNING:
            timestamp = self._next_event_timestamp(record)
            result = CancellationResult(
                handle_id=record.handle.id,
                accepted=False,
                terminal=True,
                reason_code="agent_run_already_terminal",
                timestamp=timestamp,
            )
            record.cancellation_result = result
            return result

        sequence = len(record.events) + 1
        timestamp = self._next_event_timestamp(record)
        previous_digest = (
            record.events[-1].event_digest if record.events else GENESIS_EVENT_DIGEST
        )
        payload: dict[str, JsonValue] = {
            "current_kill_switch_proof_id": str(current_kill_switch_proof_id)
        }
        event_digest = compute_agent_run_event_digest(
            run_id=record.handle.run_id,
            handle_id=record.handle.id,
            sequence=sequence,
            timestamp=timestamp,
            event_type=AgentRunEventType.CANCELLED,
            redacted_payload=payload,
            provider_event_id=None,
            previous_event_digest=previous_digest,
        )
        record.events.append(
            AgentRunEvent(
                run_id=record.handle.run_id,
                handle_id=record.handle.id,
                sequence=sequence,
                timestamp=timestamp,
                event_type=AgentRunEventType.CANCELLED,
                redacted_payload=payload,
                previous_event_digest=previous_digest,
                event_digest=event_digest,
            )
        )
        record.handle = record.handle.model_copy(update={"state": AgentRunState.CANCELLED})
        result = CancellationResult(
            handle_id=record.handle.id,
            accepted=True,
            terminal=True,
            reason_code="agent_run_cancelled",
            timestamp=timestamp,
        )
        record.cancellation_result = result
        return result

    async def resume(
        self,
        handle: AgentRunHandle,
        request_with_fresh_proofs: AgentRunRequest,
    ) -> AgentRunHandle:
        record = self._known_record(handle)
        if request_with_fresh_proofs.run_id != record.handle.run_id:
            raise AgentRuntimeError(
                "resume_run_substitution",
                "resume request must preserve the run identity",
            )
        if request_with_fresh_proofs.provider_binding_id != record.handle.provider_binding_id:
            raise AgentRuntimeError(
                "resume_provider_binding_substitution",
                "resume request must preserve the provider binding identity",
            )
        if request_with_fresh_proofs.resume_handle_id != record.handle.id:
            raise AgentRuntimeError(
                "resume_handle_substitution",
                "resume request must reference the current handle",
            )
        if record.handle.state is not AgentRunState.RUNNING:
            raise AgentRuntimeError(
                "agent_run_terminal",
                "terminal agent runs cannot be resumed",
            )
        self._validate_binding_scope(
            request_with_fresh_proofs,
            self._bindings[record.handle.provider_binding_id],
        )
        return record.handle

    def _known_binding(self, binding: ProviderBinding) -> ProviderBinding:
        known = self._bindings.get(binding.id)
        if known is None:
            raise AgentRuntimeError(
                "unknown_provider_binding",
                "provider binding is not registered",
            )
        if known != binding:
            raise AgentRuntimeError(
                "provider_binding_substitution",
                "provider binding fields do not match the registered binding",
            )
        return known

    @staticmethod
    def _snapshot_template(template: SimulatedEventTemplate) -> SimulatedEventTemplate:
        return SimulatedEventTemplate(
            event_type=template.event_type,
            redacted_payload=deepcopy(dict(template.redacted_payload)),
            provider_event_id=template.provider_event_id,
        )

    def _binding_for_start(self, request: AgentRunRequest) -> ProviderBinding:
        binding = self._bindings.get(request.provider_binding_id)
        if binding is None:
            raise AgentRuntimeError(
                "unknown_provider_binding",
                "provider binding is not registered",
            )
        if binding.status is not ProviderStatus.AVAILABLE:
            raise AgentRuntimeError(
                "provider_binding_unavailable",
                "provider binding is not available",
            )
        self._validate_binding_scope(request, binding)
        return binding

    @staticmethod
    def _validate_binding_scope(request: AgentRunRequest, binding: ProviderBinding) -> None:
        if request.workspace_id != binding.workspace_id:
            raise AgentRuntimeError(
                "provider_binding_workspace_mismatch",
                "provider binding belongs to another workspace",
            )
        if request.project_id != binding.project_id:
            raise AgentRuntimeError(
                "provider_binding_project_mismatch",
                "provider binding belongs to another project scope",
            )

    def _materialize_events(
        self,
        *,
        request: AgentRunRequest,
        handle_id: UUID,
        binding: ProviderBinding,
    ) -> tuple[list[AgentRunEvent], AgentRunState]:
        events: list[AgentRunEvent] = []
        previous_digest = GENESIS_EVENT_DIGEST
        state = AgentRunState.RUNNING
        terminal_seen = False
        templates = self._event_templates.get(binding.id, ())
        for sequence, template in enumerate(templates, start=1):
            if terminal_seen:
                raise AgentRuntimeError(
                    "event_after_terminal",
                    "event template contains an event after a terminal event",
                )
            timestamp = binding.health_checked_at + timedelta(microseconds=sequence - 1)
            payload = dict(template.redacted_payload)
            event_digest = compute_agent_run_event_digest(
                run_id=request.run_id,
                handle_id=handle_id,
                sequence=sequence,
                timestamp=timestamp,
                event_type=template.event_type,
                redacted_payload=payload,
                provider_event_id=template.provider_event_id,
                previous_event_digest=previous_digest,
            )
            event = AgentRunEvent(
                run_id=request.run_id,
                handle_id=handle_id,
                sequence=sequence,
                timestamp=timestamp,
                event_type=template.event_type,
                redacted_payload=payload,
                provider_event_id=template.provider_event_id,
                previous_event_digest=previous_digest,
                event_digest=event_digest,
            )
            events.append(event)
            previous_digest = event.event_digest
            terminal_state = _TERMINAL_EVENT_STATES.get(event.event_type)
            if terminal_state is not None:
                state = terminal_state
                terminal_seen = True
        return events, state

    def _known_record(self, handle: AgentRunHandle) -> _RunRecord:
        record = self._runs.get(handle.id)
        if record is None:
            raise AgentRuntimeError(
                "unknown_agent_run_handle",
                "agent run handle is not registered",
            )
        if (
            handle.run_id != record.handle.run_id
            or handle.provider_binding_id != record.handle.provider_binding_id
        ):
            raise AgentRuntimeError(
                "agent_run_handle_substitution",
                "agent run handle fields do not match the registered handle",
            )
        return record

    @staticmethod
    def _next_event_timestamp(record: _RunRecord) -> datetime:
        return record.handle.created_at + timedelta(microseconds=len(record.events))
