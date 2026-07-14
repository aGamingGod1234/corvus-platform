from __future__ import annotations

import secrets
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from corvus.mvp.api import create_app


def _client(database: Path) -> tuple[TestClient, str]:
    bootstrap_token = secrets.token_urlsafe(32)
    app = create_app(
        database=database,
        bootstrap_token=bootstrap_token,
        session_secret=secrets.token_bytes(32),
        replay_limit=100,
    )
    return TestClient(app), bootstrap_token


def _pair(client: TestClient, bootstrap_token: str) -> str:
    response = client.post("/api/auth/pair", json={"token": bootstrap_token})
    assert response.status_code == 200, response.text
    session = client.get("/api/auth/session")
    assert session.status_code == 200, session.text
    return cast(str, session.json()["csrf_token"])


def test_pairing_session_authorization_and_csrf(tmp_path: Path) -> None:
    client, bootstrap_token = _client(tmp_path / "corvus.sqlite3")

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/auth/pair", json={"token": "wrong"}).status_code == 403

    csrf = _pair(client, bootstrap_token)
    assert client.post("/api/projects", json={"name": "No CSRF"}).status_code == 403
    created = client.post(
        "/api/projects",
        json={"name": "API project"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201, created.text
    assert created.json()["tenant_id"] == "local"
    assert client.get("/api/projects").json()[0]["name"] == "API project"
    assert client.get("/openapi.json").status_code == 200


def test_http_workflow_execution_and_sse_replay(tmp_path: Path) -> None:
    client, bootstrap_token = _client(tmp_path / "corvus.sqlite3")
    csrf = _pair(client, bootstrap_token)
    mutation_headers = {"X-CSRF-Token": csrf}
    project = client.post(
        "/api/projects",
        json={"name": "HTTP workflow"},
        headers=mutation_headers,
    ).json()
    outcome_response = client.post(
        f"/api/projects/{project['id']}/outcomes",
        json={"title": "Execute over HTTP", "acceptance_criteria": ["two items complete"]},
        headers=mutation_headers,
    )
    assert outcome_response.status_code == 201, outcome_response.text
    outcome = outcome_response.json()
    workflow_response = client.post(
        f"/api/outcomes/{outcome['id']}/workflows",
        json={
            "name": "HTTP graph",
            "items": [
                {"key": "first", "title": "First"},
                {"key": "second", "title": "Second", "depends_on": ["first"]},
            ],
        },
        headers=mutation_headers,
    )
    assert workflow_response.status_code == 201, workflow_response.text
    workflow = workflow_response.json()
    workflow_id = workflow["id"]
    assert (
        client.post(f"/api/workflows/{workflow_id}/start", headers=mutation_headers).status_code
        == 200
    )
    assert (
        client.post(f"/api/workflows/{workflow_id}/run-next", headers=mutation_headers).json()[
            "key"
        ]
        == "first"
    )
    assert (
        client.post(f"/api/workflows/{workflow_id}/run-next", headers=mutation_headers).json()[
            "key"
        ]
        == "second"
    )
    assert client.get(f"/api/workflows/{workflow_id}").json()["status"] == "succeeded"

    stream = client.get(f"/api/workflows/{workflow_id}/events?follow=false")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "event: workflow.succeeded" in stream.text
    event_ids = [
        int(line.removeprefix("id: "))
        for line in stream.text.splitlines()
        if line.startswith("id: ")
    ]
    assert event_ids == sorted(event_ids)

    replay = client.get(
        f"/api/workflows/{workflow_id}/events?follow=false",
        headers={"Last-Event-ID": str(event_ids[-2])},
    )
    replay_ids = [
        int(line.removeprefix("id: "))
        for line in replay.text.splitlines()
        if line.startswith("id: ")
    ]
    assert replay_ids == [event_ids[-1]]


def test_http_approval_budget_and_duplicate_safety(tmp_path: Path) -> None:
    client, bootstrap_token = _client(tmp_path / "corvus.sqlite3")
    csrf = _pair(client, bootstrap_token)
    headers = {"X-CSRF-Token": csrf}
    project = client.post("/api/projects", json={"name": "Approval"}, headers=headers).json()
    assert (
        client.put(
            f"/api/projects/{project['id']}/budget",
            json={"limit_units": 10},
            headers=headers,
        ).status_code
        == 200
    )
    outcome = client.post(
        f"/api/projects/{project['id']}/outcomes",
        json={"title": "Approval", "acceptance_criteria": ["once"]},
        headers=headers,
    ).json()
    workflow = client.post(
        f"/api/outcomes/{outcome['id']}/workflows",
        json={
            "name": "Approval graph",
            "items": [
                {
                    "key": "apply",
                    "title": "Apply",
                    "cost_units": 4,
                    "requires_approval": True,
                    "effect": {
                        "kind": "filesystem",
                        "target": "demo/output.txt",
                        "payload": {"content": "approved"},
                    },
                }
            ],
        },
        headers=headers,
    ).json()
    workflow_id = workflow["id"]
    client.post(f"/api/workflows/{workflow_id}/start", headers=headers)
    waiting = client.post(f"/api/workflows/{workflow_id}/run-next", headers=headers)
    assert waiting.json()["status"] == "waiting_approval"
    effect = client.get(f"/api/workflows/{workflow_id}/effects").json()[0]
    first = client.post(f"/api/effects/{effect['id']}/approve", headers=headers)
    replay = client.post(f"/api/effects/{effect['id']}/approve", headers=headers)
    assert replay.json()["id"] == first.json()["id"]
    client.post(f"/api/workflows/{workflow_id}/run-next", headers=headers)
    final_effect = client.get(f"/api/workflows/{workflow_id}/effects").json()[0]
    assert final_effect["execution_count"] == 1
    budget = client.get(f"/api/projects/{project['id']}/budget").json()
    assert budget["reserved_units"] == 0
    assert budget["settled_units"] == 4
