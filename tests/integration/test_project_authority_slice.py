from __future__ import annotations

from uuid import uuid4

from corvus.application.ports import ProjectAuthorizationDecision
from corvus.application.projects import (
    CreateProjectCommand,
    GetProjectQuery,
    InProcessProjectClient,
    ProjectService,
)
from corvus.domain.identity import Project


class FakeStore:
    def __init__(self) -> None:
        self.projects = {}
        self.create_calls = 0

    def create(self, project: Project) -> None:
        self.create_calls += 1
        self.projects[(project.workspace_id, project.id)] = project

    def get(self, workspace_id, project_id):
        return self.projects.get((workspace_id, project_id))


class FakeAuthorization:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow

    def authorize(self, request):
        return ProjectAuthorizationDecision(
            allowed=self.allow,
            reason_code="authorized" if self.allow else "no_requester_grant",
            authorization_snapshot_id=uuid4(),
        )


class FakeAudit:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events = []

    def record(self, event) -> None:
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.events.append(event)


def _command(project: Project) -> CreateProjectCommand:
    return CreateProjectCommand(
        request_id=uuid4(),
        workspace_id=project.workspace_id,
        requester_id=uuid4(),
        acting_agent_id=uuid4(),
        project=project,
    )


def test_create_and_read_share_one_authorized_audited_path() -> None:
    store = FakeStore()
    audit = FakeAudit()
    client = InProcessProjectClient(
        ProjectService(store=store, authorization=FakeAuthorization(), audit=audit)
    )
    project = Project(
        workspace_id=uuid4(),
        name="Corvus",
        root_locator="workspace://corvus",
        privacy="private",
    )

    created = client.create_project(_command(project))
    read = client.get_project(
        GetProjectQuery(
            request_id=uuid4(),
            workspace_id=project.workspace_id,
            requester_id=uuid4(),
            acting_agent_id=uuid4(),
            project_id=project.id,
        )
    )

    assert created.ok is True
    assert read.ok is True
    assert created.project == project
    assert read.project == project
    assert [event.action for event in audit.events] == ["project.create", "project.read"]


def test_denial_is_audited_and_does_not_mutate() -> None:
    store = FakeStore()
    audit = FakeAudit()
    client = InProcessProjectClient(
        ProjectService(store=store, authorization=FakeAuthorization(allow=False), audit=audit)
    )
    project = Project(
        workspace_id=uuid4(),
        name="Denied",
        root_locator="workspace://denied",
        privacy="private",
    )

    response = client.create_project(_command(project))

    assert response.ok is False
    assert response.reason_code == "no_requester_grant"
    assert response.project is None
    assert store.create_calls == 0
    assert audit.events[0].decision == "deny"


def test_audit_failure_fails_closed_before_mutation() -> None:
    store = FakeStore()
    client = InProcessProjectClient(
        ProjectService(
            store=store,
            authorization=FakeAuthorization(),
            audit=FakeAudit(fail=True),
        )
    )
    project = Project(
        workspace_id=uuid4(),
        name="No audit",
        root_locator="workspace://no-audit",
        privacy="private",
    )

    response = client.create_project(_command(project))

    assert response.ok is False
    assert response.reason_code == "audit_persistence_failed"
    assert store.create_calls == 0
