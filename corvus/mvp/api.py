import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from corvus.mvp.core import CorvusService, DomainConflict, DomainNotFound
from corvus.mvp.deployment import TenantScopedQueries
from corvus.mvp.models import WorkItemDefinition

_SESSION_COOKIE = "corvus_session"
_SESSION_LIFETIME = timedelta(hours=12)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PairRequest(ApiModel):
    token: str = Field(min_length=1)


class ProjectCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)


class OutcomeCreateRequest(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    acceptance_criteria: tuple[str, ...] = Field(min_length=1)


class WorkflowCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    items: tuple[WorkItemDefinition, ...] = Field(min_length=1)


class BudgetUpdateRequest(ApiModel):
    limit_units: int = Field(ge=0)


class SessionPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    username: str
    tenant_id: str
    csrf_token: str
    expires_at: datetime


class _AuthManager:
    def __init__(
        self,
        *,
        service: CorvusService,
        bootstrap_token: str,
        session_secret: bytes,
    ) -> None:
        if len(session_secret) < 32:
            raise ValueError("session_secret_must_be_at_least_32_bytes")
        self.service = service
        self.bootstrap_digest = hashlib.sha256(bootstrap_token.encode("utf-8")).digest()
        self.session_secret = session_secret

    def pair(self, token: str) -> tuple[SessionPrincipal, str]:
        candidate = hashlib.sha256(token.encode("utf-8")).digest()
        if not hmac.compare_digest(candidate, self.bootstrap_digest):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="pairing_token_invalid"
            )
        now = datetime.now(UTC)
        with self.service.store.transaction() as connection:
            existing = connection.execute("SELECT * FROM mvp_local_users LIMIT 1").fetchone()
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="pairing_already_completed",
                )
            user_id = str(uuid4())
            connection.execute(
                "INSERT INTO mvp_local_users(id, tenant_id, username, paired_at) "
                "VALUES (?, 'local', 'local-user', ?)",
                (user_id, now.isoformat()),
            )
        principal = SessionPrincipal(
            user_id=user_id,
            username="local-user",
            tenant_id="local",
            csrf_token=secrets.token_urlsafe(24),
            expires_at=now + _SESSION_LIFETIME,
        )
        return principal, self._encode(principal)

    def authenticate(self, token: str | None) -> SessionPrincipal:
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication_required"
            )
        try:
            payload_encoded, signature_encoded = token.split(".", 1)
            payload = base64.urlsafe_b64decode(_pad_base64(payload_encoded))
            signature = base64.urlsafe_b64decode(_pad_base64(signature_encoded))
        except (ValueError, TypeError) as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="session_invalid",
            ) from error
        expected = hmac.new(self.session_secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session_invalid")
        try:
            principal = SessionPrincipal.model_validate_json(payload)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="session_invalid",
            ) from error
        if principal.expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session_expired")
        with self.service.store.connect() as connection:
            row = connection.execute(
                "SELECT id FROM mvp_local_users WHERE id = ? AND tenant_id = ?",
                (principal.user_id, principal.tenant_id),
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="session_principal_revoked",
                )
        return principal

    def _encode(self, principal: SessionPrincipal) -> str:
        payload = principal.model_dump_json().encode("utf-8")
        signature = hmac.new(self.session_secret, payload, hashlib.sha256).digest()
        return f"{_base64(payload)}.{_base64(signature)}"


def _base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _pad_base64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")


def create_app(
    *,
    database: Path,
    bootstrap_token: str,
    session_secret: bytes,
    replay_limit: int = 500,
) -> FastAPI:
    if replay_limit < 1:
        raise ValueError("replay_limit_must_be_positive")
    service = CorvusService.open(database)
    auth = _AuthManager(
        service=service,
        bootstrap_token=bootstrap_token,
        session_secret=session_secret,
    )
    app = FastAPI(title="Corvus Hackathon MVP API", version="0.2.0-hackathon")

    @app.exception_handler(DomainNotFound)
    async def not_found_handler(_request: Request, error: DomainNotFound) -> JSONResponse:
        return _error_response(status.HTTP_404_NOT_FOUND, "not_found", str(error))

    @app.exception_handler(DomainConflict)
    async def conflict_handler(_request: Request, error: DomainConflict) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, "conflict", str(error))

    def authenticated(request: Request) -> SessionPrincipal:
        return auth.authenticate(request.cookies.get(_SESSION_COOKIE))

    def mutation_authorized(
        request: Request,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> SessionPrincipal:
        if csrf_token is None or not secrets.compare_digest(csrf_token, principal.csrf_token):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_invalid")
        origin = request.headers.get("origin")
        if origin is not None and origin not in {
            "http://127.0.0.1:8080",
            "http://localhost:8080",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        }:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="origin_forbidden")
        return principal

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        with service.store.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ready"}

    @app.post("/api/auth/pair")
    def pair(body: PairRequest, response: Response) -> dict[str, str]:
        principal, token = auth.pair(body.token)
        response.set_cookie(
            _SESSION_COOKIE,
            token,
            max_age=int(_SESSION_LIFETIME.total_seconds()),
            httponly=True,
            secure=False,
            samesite="strict",
            path="/",
        )
        return {"status": "paired", "username": principal.username}

    @app.get("/api/auth/session")
    def session(
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> dict[str, Any]:
        return principal.model_dump(mode="json")

    @app.get("/api/projects")
    def projects(
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        queries = TenantScopedQueries(service.store)
        return [item.model_dump(mode="json") for item in queries.list_projects(principal.tenant_id)]

    @app.post("/api/projects", status_code=status.HTTP_201_CREATED)
    def create_project(
        body: ProjectCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        project = service.create_project(name=body.name, tenant_id=principal.tenant_id)
        return project.model_dump(mode="json")

    @app.post(
        "/api/projects/{project_id}/outcomes",
        status_code=status.HTTP_201_CREATED,
    )
    def create_outcome(
        project_id: str,
        body: OutcomeCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        outcome = service.create_outcome(
            project_id=project_id,
            title=body.title,
            acceptance_criteria=body.acceptance_criteria,
        )
        return outcome.model_dump(mode="json")

    @app.post(
        "/api/outcomes/{outcome_id}/workflows",
        status_code=status.HTTP_201_CREATED,
    )
    def create_workflow(
        outcome_id: str,
        body: WorkflowCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_outcome_tenant(service, outcome_id, principal.tenant_id)
        workflow = service.create_workflow(
            outcome_id=outcome_id,
            name=body.name,
            items=body.items,
        )
        return workflow.model_dump(mode="json")

    @app.get("/api/workflows/{workflow_id}")
    def workflow(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.get_workflow(workflow_id).model_dump(mode="json")

    @app.get("/api/workflows/{workflow_id}/work-items")
    def work_items(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [item.model_dump(mode="json") for item in service.list_work_items(workflow_id)]

    @app.post("/api/workflows/{workflow_id}/start")
    def start_workflow(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.start_workflow(workflow_id).model_dump(mode="json")

    @app.post("/api/workflows/{workflow_id}/run-next")
    def run_next(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        item = service.run_next(workflow_id, worker_id=f"api:{principal.user_id}")
        if item is None:
            raise DomainConflict("no_ready_work_item")
        return item.model_dump(mode="json")

    @app.get("/api/workflows/{workflow_id}/effects")
    def effects(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [effect.model_dump(mode="json") for effect in service.list_effects(workflow_id)]

    @app.post("/api/effects/{effect_id}/approve")
    def approve_effect(
        effect_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_effect_tenant(service, effect_id, principal.tenant_id)
        return service.approve_effect(effect_id, actor_id=principal.user_id).model_dump(mode="json")

    @app.put("/api/projects/{project_id}/budget")
    def set_budget(
        project_id: str,
        body: BudgetUpdateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return service.set_budget(project_id, limit_units=body.limit_units).model_dump(mode="json")

    @app.get("/api/projects/{project_id}/budget")
    def get_budget(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return service.get_budget(project_id).model_dump(mode="json")

    @app.get("/api/workflows/{workflow_id}/artifacts")
    def artifacts(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [item.model_dump(mode="json") for item in service.list_artifacts(workflow_id)]

    @app.get("/api/workflows/{workflow_id}/conversation")
    def conversation(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [
            item.model_dump(mode="json") for item in service.list_conversation_entries(workflow_id)
        ]

    @app.get("/api/workflows/{workflow_id}/events")
    async def events(
        workflow_id: str,
        request: Request,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
        follow: bool = True,
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        cursor = _parse_event_cursor(last_event_id)
        return StreamingResponse(
            _event_stream(
                service,
                workflow_id=workflow_id,
                request=request,
                cursor=cursor,
                follow=follow,
                replay_limit=replay_limit,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _parse_event_cursor(value: str | None) -> int:
    if value is None:
        return 0
    try:
        cursor = int(value)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="last_event_id_invalid") from error
    if cursor < 0:
        raise HTTPException(status_code=400, detail="last_event_id_invalid")
    return cursor


async def _event_stream(
    service: CorvusService,
    *,
    workflow_id: str,
    request: Request,
    cursor: int,
    follow: bool,
    replay_limit: int,
) -> AsyncIterator[str]:
    current = cursor
    while True:
        events = service.list_events(workflow_id, after_id=current)
        if len(events) > replay_limit:
            latest = int(events[-1]["id"])
            yield _sse(
                event="resync_required",
                data={"reason": "cursor_too_old", "latest_event_id": latest},
            )
            return
        for event in events:
            event_id = int(event["id"])
            yield _sse(
                event_id=event_id,
                event=str(event["event_type"]),
                data=event,
            )
            current = event_id
        if not follow or await request.is_disconnected():
            return
        await asyncio.sleep(0.25)


def _sse(
    *,
    event: str,
    data: dict[str, Any],
    event_id: int | None = None,
) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'), sort_keys=True)}")
    return "\n".join(lines) + "\n\n"


def _require_outcome_tenant(service: CorvusService, outcome_id: str, tenant_id: str) -> None:
    with service.store.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM mvp_outcomes o JOIN mvp_projects p ON p.id = o.project_id "
            "WHERE o.id = ? AND p.tenant_id = ?",
            (outcome_id, tenant_id),
        ).fetchone()
        if row is None:
            raise DomainNotFound("outcome_not_found")


def _require_workflow_tenant(service: CorvusService, workflow_id: str, tenant_id: str) -> None:
    with service.store.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM mvp_workflows w JOIN mvp_outcomes o ON o.id = w.outcome_id "
            "JOIN mvp_projects p ON p.id = o.project_id WHERE w.id = ? AND p.tenant_id = ?",
            (workflow_id, tenant_id),
        ).fetchone()
        if row is None:
            raise DomainNotFound("workflow_not_found")


def _require_effect_tenant(service: CorvusService, effect_id: str, tenant_id: str) -> None:
    with service.store.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM mvp_effects e JOIN mvp_workflows w ON w.id = e.workflow_id "
            "JOIN mvp_outcomes o ON o.id = w.outcome_id "
            "JOIN mvp_projects p ON p.id = o.project_id WHERE e.id = ? AND p.tenant_id = ?",
            (effect_id, tenant_id),
        ).fetchone()
        if row is None:
            raise DomainNotFound("effect_not_found")
