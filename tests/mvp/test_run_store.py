from __future__ import annotations

from pathlib import Path

import pytest

from corvus.mvp.run_models import RunStatus, StartRunRequest
from corvus.mvp.run_store import RunStore, RunStoreConflict, RunStoreNotFound
from corvus.mvp.store import SqliteStore


def _repository(store: SqliteStore, tenant_id: str = "tenant-a") -> str:
    # RunStore only requires an existing tenant-scoped repository row; Git behavior is tested elsewhere.
    with store.transaction() as connection:
        connection.execute(
            "INSERT INTO mvp_repositories "
            "(id, tenant_id, canonical_path, display_name, remote_slug, default_branch, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, NULL, 'main', ?, ?)",
            (
                "11111111-1111-4111-8111-111111111111",
                tenant_id,
                "C:/test/repository",
                "Repository",
                "2026-07-18T00:00:00+00:00",
                "2026-07-18T00:00:00+00:00",
            ),
        )
    return "11111111-1111-4111-8111-111111111111"


def _request(repository_id: str) -> StartRunRequest:
    return StartRunRequest(
        repository_id=repository_id,
        task="Implement the durable run store",
        provider="codex",
        model="gpt-5.6-codex",
        effort="high",
        mode="build",
        safety_digest="a" * 64,
        output_policy="prepare_contribution",
    )


def test_persists_runs_events_and_evidence_across_restart(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "corvus.sqlite3")
    repository_id = _repository(store)
    runs = RunStore(store)

    created = runs.create("tenant-a", _request(repository_id), base_sha="b" * 40)
    running = runs.transition("tenant-a", created.id, RunStatus.RUNNING)
    first = runs.append_event(created.id, "provider.started", {"message": "Started"})
    second = runs.append_event(created.id, "provider.output", {"message": "Working"})
    evidence = runs.add_evidence(created.id, "test", "12 tests passed", "c" * 64)

    restarted = RunStore(SqliteStore(tmp_path / "corvus.sqlite3"))
    loaded = restarted.get("tenant-a", created.id)
    assert loaded.status == RunStatus.RUNNING
    assert running.started_at is not None
    assert [event.sequence for event in restarted.events("tenant-a", created.id)] == [1, 2]
    assert first.sequence == 1 and second.sequence == 2
    assert restarted.evidence("tenant-a", created.id) == (evidence,)


def test_rejects_invalid_transitions_and_keeps_terminal_state(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "corvus.sqlite3")
    repository_id = _repository(store)
    runs = RunStore(store)
    created = runs.create("tenant-a", _request(repository_id), base_sha="b" * 40)

    with pytest.raises(RunStoreConflict, match="run_transition_invalid"):
        runs.transition("tenant-a", created.id, RunStatus.PUBLISHED)

    runs.transition("tenant-a", created.id, RunStatus.RUNNING)
    failed = runs.transition("tenant-a", created.id, RunStatus.FAILED)
    assert failed.finished_at is not None
    with pytest.raises(RunStoreConflict, match="run_transition_invalid"):
        runs.transition("tenant-a", created.id, RunStatus.RUNNING)


def test_retry_links_a_new_run_without_mutating_original(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "corvus.sqlite3")
    repository_id = _repository(store)
    runs = RunStore(store)
    original = runs.create("tenant-a", _request(repository_id), base_sha="b" * 40)
    runs.transition("tenant-a", original.id, RunStatus.FAILED)

    retry = runs.retry("tenant-a", original.id)

    assert retry.id != original.id
    assert retry.retry_of_run_id == original.id
    assert retry.status == RunStatus.PREPARING
    assert runs.get("tenant-a", original.id).status == RunStatus.FAILED


def test_occurrence_is_unique_and_tenant_scope_is_enforced(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "corvus.sqlite3")
    repository_id = _repository(store)
    runs = RunStore(store)
    request = _request(repository_id).model_copy(
        update={"schedule_id": "schedule-1", "occurrence_key": "2026-07-18T09:00:00Z"}
    )
    created = runs.create("tenant-a", request, base_sha="b" * 40)

    with pytest.raises(RunStoreConflict, match="run_occurrence_exists"):
        runs.create("tenant-a", request, base_sha="b" * 40)
    with pytest.raises(RunStoreNotFound, match="run_not_found"):
        runs.get("tenant-b", created.id)
    assert runs.list("tenant-b") == ()
