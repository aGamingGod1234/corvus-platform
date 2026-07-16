import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from corvus.mvp.core import CorvusService, DomainConflict, DomainNotFound
from corvus.mvp.deployment import TenantScopedQueries
from corvus.mvp.governance import (
    AutonomyDecision,
    GovernanceService,
    MemoryEntry,
    ProviderConnection,
    RetrievedMemory,
    Routine,
    RoutineRun,
    SkillVersion,
    Team,
    TeamMember,
)
from corvus.mvp.ingress import (
    ChannelEventEnvelope,
    ChannelEventRecord,
    ChannelIngressService,
    LocalEnvelopeSigner,
    OfflineConnectorService,
    OfflineIntentRecord,
)
from corvus.mvp.models import (
    ApprovalRecord,
    ArtifactRecord,
    BudgetAccount,
    ConversationEntry,
    EffectRecord,
    OutcomeContract,
    Project,
    Workflow,
    WorkItem,
    WorkItemDefinition,
)
from corvus.platform.api import IdentityApiDependencies, create_platform_router
from corvus.platform.api.dependencies import build_hosted_identity_dependencies_from_env

_SESSION_COOKIE = "corvus_session"
_SESSION_LIFETIME = timedelta(hours=12)
_INSTANCE_CHALLENGE_HEADER = "X-Corvus-Challenge"
_INSTANCE_PROOF_HEADER = "X-Corvus-Instance-Proof"
_MINIMUM_INSTANCE_CHALLENGE_LENGTH = 16
_MAXIMUM_INSTANCE_CHALLENGE_LENGTH = 512
_WEB_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PairRequest(ApiModel):
    token: str = Field(min_length=1)


class PairResponse(ApiModel):
    status: str
    username: str


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


class ToggleRequest(ApiModel):
    enabled: bool


class KillSwitchResponse(ApiModel):
    scope_kind: str
    scope_id: str
    enabled: bool


class TeamCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)


class TeamMemberRequest(ApiModel):
    principal_id: str = Field(min_length=1)
    role: Literal["owner", "operator", "viewer"]


class ProviderCreateRequest(ApiModel):
    provider: str = Field(min_length=1, max_length=100)
    credential_ref: str = Field(min_length=1, max_length=500)


class AutonomyEvaluateRequest(ApiModel):
    capability: str = Field(min_length=1, max_length=200)
    requested_execution: bool


class MemoryCreateRequest(ApiModel):
    scope: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=20_000)


class SkillCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)


class RoutineCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    skill_version_id: str = Field(min_length=1)


class EnvelopeActorRequest(ApiModel):
    actor_id: str = Field(min_length=1, max_length=200)
    public_key: str = Field(min_length=1, max_length=1_000)


class ChannelIdentityRequest(ApiModel):
    provider: str = Field(min_length=1, max_length=100)
    external_id: str = Field(min_length=1, max_length=200)
    principal_id: str = Field(min_length=1, max_length=200)


class MutationStatus(ApiModel):
    status: str


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
        allow_existing_user_pairing: bool,
    ) -> None:
        if len(session_secret) < 32:
            raise ValueError("session_secret_must_be_at_least_32_bytes")
        self.service = service
        self.bootstrap_digest = hashlib.sha256(bootstrap_token.encode("utf-8")).digest()
        self.session_secret = session_secret
        self.allow_existing_user_pairing = allow_existing_user_pairing
        self._bootstrap_lock = Lock()
        self._bootstrap_used = False

    def pair(self, token: str) -> tuple[SessionPrincipal, str]:
        candidate = hashlib.sha256(token.encode("utf-8")).digest()
        if not hmac.compare_digest(candidate, self.bootstrap_digest):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="pairing_token_invalid"
            )
        with self._bootstrap_lock:
            if self._bootstrap_used:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="pairing_token_consumed",
                )
            self._bootstrap_used = True
            now = datetime.now(UTC)
            with self.service.store.transaction() as connection:
                existing = connection.execute("SELECT * FROM mvp_local_users LIMIT 1").fetchone()
                if existing is not None and not self.allow_existing_user_pairing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="pairing_already_completed",
                    )
                if existing is None:
                    user_id = str(uuid4())
                    tenant_id = "local"
                    username = "local-user"
                    connection.execute(
                        "INSERT INTO mvp_local_users(id, tenant_id, username, paired_at) "
                        "VALUES (?, ?, ?, ?)",
                        (user_id, tenant_id, username, now.isoformat()),
                    )
                else:
                    user_id = existing["id"]
                    tenant_id = existing["tenant_id"]
                    username = existing["username"]
        principal = SessionPrincipal(
            user_id=user_id,
            username=username,
            tenant_id=tenant_id,
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


async def _security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = _WEB_CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def create_app(
    *,
    database: Path,
    bootstrap_token: str,
    session_secret: bytes,
    replay_limit: int = 500,
    static_web_dir: Path | None = None,
    allowed_origins: frozenset[str] | None = None,
    allow_existing_user_pairing: bool = False,
    instance_token: str | None = None,
    identity_dependencies: IdentityApiDependencies | None = None,
) -> FastAPI:
    if replay_limit < 1:
        raise ValueError("replay_limit_must_be_positive")
    if instance_token is not None and not 16 <= len(instance_token) <= 512:
        raise ValueError("instance_token_length_invalid")
    static_root = _validated_static_root(static_web_dir)
    trusted_origins = (
        allowed_origins
        if allowed_origins is not None
        else frozenset(
            {
                "http://127.0.0.1:8080",
                "http://localhost:8080",
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            }
        )
    )
    service = CorvusService.open(database)
    governance = GovernanceService(service.store)
    offline = OfflineConnectorService(
        service.store,
        signer=LocalEnvelopeSigner.generate(actor_id="local-browser-connector"),
    )
    channel = ChannelIngressService(service.store)
    auth = _AuthManager(
        service=service,
        bootstrap_token=bootstrap_token,
        session_secret=session_secret,
        allow_existing_user_pairing=allow_existing_user_pairing,
    )
    app = FastAPI(title="Corvus Hackathon MVP API", version="0.2.0-hackathon")
    app.middleware("http")(_security_headers)

    @app.exception_handler(DomainNotFound)
    async def not_found_handler(_request: Request, error: DomainNotFound) -> JSONResponse:
        return _error_response(status.HTTP_404_NOT_FOUND, "not_found", str(error))

    @app.exception_handler(DomainConflict)
    async def conflict_handler(_request: Request, error: DomainConflict) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, "conflict", str(error))

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        if request.url.path.startswith("/api/v2/"):
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "detail": {
                        "code": "invalid_request",
                        "correlation_id": str(uuid4()),
                    }
                },
            )
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_request",
            "request_validation_failed",
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, error: ValueError) -> JSONResponse:
        return _error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_request", str(error))

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
        if origin is not None and origin not in trusted_origins:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="origin_forbidden")
        return principal

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(
        response: Response,
        instance_challenge: Annotated[str | None, Header(alias=_INSTANCE_CHALLENGE_HEADER)] = None,
    ) -> dict[str, str]:
        with service.store.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        if instance_token is not None and instance_challenge is not None:
            if not (
                _MINIMUM_INSTANCE_CHALLENGE_LENGTH
                <= len(instance_challenge)
                <= _MAXIMUM_INSTANCE_CHALLENGE_LENGTH
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="instance_challenge_length_invalid",
                )
            response.headers[_INSTANCE_PROOF_HEADER] = hmac.new(
                instance_token.encode("utf-8"),
                instance_challenge.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        return {"status": "ready"}

    @app.post("/api/auth/pair", response_model=PairResponse)
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

    @app.get("/api/auth/session", response_model=SessionPrincipal)
    def session(
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> dict[str, Any]:
        return principal.model_dump(mode="json")

    @app.get("/api/projects", response_model=list[Project])
    def projects(
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        queries = TenantScopedQueries(service.store)
        return [item.model_dump(mode="json") for item in queries.list_projects(principal.tenant_id)]

    @app.post(
        "/api/projects",
        status_code=status.HTTP_201_CREATED,
        response_model=Project,
    )
    def create_project(
        body: ProjectCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        project = service.create_project(name=body.name, tenant_id=principal.tenant_id)
        return project.model_dump(mode="json")

    @app.post(
        "/api/projects/{project_id}/outcomes",
        status_code=status.HTTP_201_CREATED,
        response_model=OutcomeContract,
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

    @app.get(
        "/api/projects/{project_id}/outcomes",
        response_model=list[OutcomeContract],
    )
    def outcomes(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return [item.model_dump(mode="json") for item in service.list_outcomes(project_id)]

    @app.post(
        "/api/outcomes/{outcome_id}/workflows",
        status_code=status.HTTP_201_CREATED,
        response_model=Workflow,
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

    @app.get(
        "/api/outcomes/{outcome_id}/workflows",
        response_model=list[Workflow],
    )
    def workflows(
        outcome_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_outcome_tenant(service, outcome_id, principal.tenant_id)
        return [item.model_dump(mode="json") for item in service.list_workflows(outcome_id)]

    @app.get("/api/workflows/{workflow_id}", response_model=Workflow)
    def workflow(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.get_workflow(workflow_id).model_dump(mode="json")

    @app.get(
        "/api/workflows/{workflow_id}/work-items",
        response_model=list[WorkItem],
    )
    def work_items(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [item.model_dump(mode="json") for item in service.list_work_items(workflow_id)]

    @app.post("/api/workflows/{workflow_id}/start", response_model=Workflow)
    def start_workflow(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.start_workflow(workflow_id).model_dump(mode="json")

    @app.post("/api/workflows/{workflow_id}/pause", response_model=Workflow)
    def pause_workflow(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.pause_workflow(workflow_id).model_dump(mode="json")

    @app.post("/api/workflows/{workflow_id}/resume", response_model=Workflow)
    def resume_workflow(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.start_workflow(workflow_id).model_dump(mode="json")

    @app.post("/api/workflows/{workflow_id}/cancel", response_model=Workflow)
    def cancel_workflow(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.cancel_workflow(workflow_id).model_dump(mode="json")

    @app.post("/api/workflows/{workflow_id}/run-next", response_model=WorkItem)
    def run_next(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        item = service.run_next(workflow_id, worker_id=f"api:{principal.user_id}")
        if item is None:
            raise DomainConflict("no_ready_work_item")
        return item.model_dump(mode="json")

    @app.post(
        "/api/workflows/{workflow_id}/work-items/{item_key}/retry",
        response_model=WorkItem,
    )
    def retry_work_item(
        workflow_id: str,
        item_key: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return service.retry_work_item(workflow_id, item_key).model_dump(mode="json")

    @app.get(
        "/api/workflows/{workflow_id}/effects",
        response_model=list[EffectRecord],
    )
    def effects(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [effect.model_dump(mode="json") for effect in service.list_effects(workflow_id)]

    @app.post("/api/effects/{effect_id}/approve", response_model=ApprovalRecord)
    def approve_effect(
        effect_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_effect_tenant(service, effect_id, principal.tenant_id)
        return service.approve_effect(effect_id, actor_id=principal.user_id).model_dump(mode="json")

    @app.post("/api/effects/{effect_id}/reject", response_model=ApprovalRecord)
    def reject_effect(
        effect_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_effect_tenant(service, effect_id, principal.tenant_id)
        return service.reject_effect(effect_id, actor_id=principal.user_id).model_dump(mode="json")

    @app.put(
        "/api/workflows/{workflow_id}/kill-switch",
        response_model=KillSwitchResponse,
    )
    def set_workflow_kill_switch(
        workflow_id: str,
        body: ToggleRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        service.set_kill_switch(scope_kind="workflow", scope_id=workflow_id, enabled=body.enabled)
        return {"scope_kind": "workflow", "scope_id": workflow_id, "enabled": body.enabled}

    @app.put("/api/projects/{project_id}/budget", response_model=BudgetAccount)
    def set_budget(
        project_id: str,
        body: BudgetUpdateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return service.set_budget(project_id, limit_units=body.limit_units).model_dump(mode="json")

    @app.get("/api/projects/{project_id}/budget", response_model=BudgetAccount)
    def get_budget(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return service.get_budget(project_id).model_dump(mode="json")

    @app.get(
        "/api/workflows/{workflow_id}/artifacts",
        response_model=list[ArtifactRecord],
    )
    def artifacts(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [item.model_dump(mode="json") for item in service.list_artifacts(workflow_id)]

    @app.get(
        "/api/workflows/{workflow_id}/conversation",
        response_model=list[ConversationEntry],
    )
    def conversation(
        workflow_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        _require_workflow_tenant(service, workflow_id, principal.tenant_id)
        return [
            item.model_dump(mode="json") for item in service.list_conversation_entries(workflow_id)
        ]

    @app.get("/api/projects/{project_id}/teams", response_model=list[Team])
    def teams(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return [item.model_dump(mode="json") for item in governance.list_teams(project_id)]

    @app.post(
        "/api/projects/{project_id}/teams",
        status_code=status.HTTP_201_CREATED,
        response_model=Team,
    )
    def create_team(
        project_id: str,
        body: TeamCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return governance.create_team(
            project_id=project_id,
            name=body.name,
            owner_id=principal.user_id,
        ).model_dump(mode="json")

    @app.get("/api/teams/{team_id}/members", response_model=list[TeamMember])
    def team_members(
        team_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        members = governance.list_team_members(team_id)
        _require_team_tenant(service, governance, team_id, principal.tenant_id)
        return [item.model_dump(mode="json") for item in members]

    @app.post("/api/teams/{team_id}/members", response_model=MutationStatus)
    def add_team_member(
        team_id: str,
        body: TeamMemberRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, str]:
        _require_team_tenant(service, governance, team_id, principal.tenant_id)
        governance.add_member(
            team_id,
            actor_id=principal.user_id,
            principal_id=body.principal_id,
            role=body.role,
        )
        return {"status": "member_added"}

    @app.get(
        "/api/projects/{project_id}/providers",
        response_model=list[ProviderConnection],
    )
    def providers(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return [
            item.model_dump(mode="json")
            for item in governance.list_provider_connections(project_id)
        ]

    @app.post(
        "/api/projects/{project_id}/providers",
        status_code=status.HTTP_201_CREATED,
        response_model=ProviderConnection,
    )
    def create_provider(
        project_id: str,
        body: ProviderCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return governance.create_provider_connection(
            project_id=project_id,
            provider=body.provider,
            credential_ref=body.credential_ref,
        ).model_dump(mode="json")

    @app.post(
        "/api/projects/{project_id}/autonomy/evaluate",
        response_model=AutonomyDecision,
    )
    def evaluate_autonomy(
        project_id: str,
        body: AutonomyEvaluateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return governance.evaluate_autonomy(
            project_id=project_id,
            principal_id=principal.user_id,
            capability=body.capability,
            requested_execution=body.requested_execution,
        ).model_dump(mode="json")

    @app.get("/api/projects/{project_id}/memories", response_model=list[MemoryEntry])
    def memories(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return [item.model_dump(mode="json") for item in governance.list_memory_entries(project_id)]

    @app.post(
        "/api/projects/{project_id}/memories",
        status_code=status.HTTP_201_CREATED,
        response_model=MemoryEntry,
    )
    def store_memory(
        project_id: str,
        body: MemoryCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return governance.store_memory(
            project_id=project_id,
            scope=body.scope,
            content=body.content,
            provenance=f"user:{principal.user_id}",
        ).model_dump(mode="json")

    @app.get(
        "/api/projects/{project_id}/memories/retrieve",
        response_model=list[RetrievedMemory],
    )
    def retrieve_memory(
        project_id: str,
        query: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return [
            item.model_dump(mode="json")
            for item in governance.retrieve_memory(project_id=project_id, query=query)
        ]

    @app.get("/api/projects/{project_id}/skills", response_model=list[SkillVersion])
    def skills(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return [item.model_dump(mode="json") for item in governance.list_skills(project_id)]

    @app.post(
        "/api/projects/{project_id}/skills",
        status_code=status.HTTP_201_CREATED,
        response_model=SkillVersion,
    )
    def create_skill(
        project_id: str,
        body: SkillCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return governance.create_skill(
            project_id=project_id,
            name=body.name,
            content=body.content,
        ).model_dump(mode="json")

    @app.post("/api/skills/{skill_id}/activate", response_model=SkillVersion)
    def activate_skill(
        skill_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        skill = governance.get_skill(skill_id)
        TenantScopedQueries(service.store).get_project(principal.tenant_id, skill.project_id)
        return governance.activate_skill(skill_id).model_dump(mode="json")

    @app.get("/api/projects/{project_id}/routines", response_model=list[Routine])
    def routines(
        project_id: str,
        principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return [item.model_dump(mode="json") for item in governance.list_routines(project_id)]

    @app.post(
        "/api/projects/{project_id}/routines",
        status_code=status.HTTP_201_CREATED,
        response_model=Routine,
    )
    def create_routine(
        project_id: str,
        body: RoutineCreateRequest,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        TenantScopedQueries(service.store).get_project(principal.tenant_id, project_id)
        return governance.create_routine(
            project_id=project_id,
            name=body.name,
            skill_version_id=body.skill_version_id,
        ).model_dump(mode="json")

    @app.post("/api/routines/{routine_id}/run", response_model=RoutineRun)
    def run_routine(
        routine_id: str,
        principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, Any]:
        routine = governance.get_routine(routine_id)
        TenantScopedQueries(service.store).get_project(principal.tenant_id, routine.project_id)
        return governance.run_routine(routine_id, actor_id=principal.user_id).model_dump(
            mode="json"
        )

    @app.get("/api/offline-intents", response_model=list[OfflineIntentRecord])
    def offline_intents(
        _principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in offline.list_intents()]

    @app.post("/api/channel/actors", response_model=MutationStatus)
    def register_channel_actor(
        body: EnvelopeActorRequest,
        _principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, str]:
        channel.register_actor(body.actor_id, body.public_key)
        return {"status": "actor_registered"}

    @app.post("/api/channel/identities", response_model=MutationStatus)
    def map_channel_identity(
        body: ChannelIdentityRequest,
        _principal: Annotated[SessionPrincipal, Depends(mutation_authorized)],
    ) -> dict[str, str]:
        channel.map_identity(
            provider=body.provider,
            external_id=body.external_id,
            principal_id=body.principal_id,
        )
        return {"status": "identity_mapped"}

    @app.post("/api/channel/events", response_model=ChannelEventRecord)
    def ingest_channel_event(body: ChannelEventEnvelope) -> dict[str, Any]:
        return channel.ingest(body).model_dump(mode="json")

    @app.get("/api/channel/events", response_model=list[ChannelEventRecord])
    def channel_events(
        _principal: Annotated[SessionPrincipal, Depends(authenticated)],
    ) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in channel.list_events()]

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

    hosted_identity = (
        identity_dependencies
        if identity_dependencies is not None
        else build_hosted_identity_dependencies_from_env()
    )
    app.include_router(create_platform_router(hosted_identity))

    if static_root is not None:
        app.mount("/", StaticFiles(directory=static_root, html=True), name="operator-console")

    return app


def _validated_static_root(static_web_dir: Path | None) -> Path | None:
    if static_web_dir is None:
        return None
    root = static_web_dir.expanduser().resolve()
    index = root / "index.html"
    if not root.is_dir() or not index.is_file() or not index.resolve().is_relative_to(root):
        raise ValueError("static_web_index_missing")
    return root


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


def _require_team_tenant(
    service: CorvusService,
    governance: GovernanceService,
    team_id: str,
    tenant_id: str,
) -> None:
    team = governance.get_team(team_id)
    TenantScopedQueries(service.store).get_project(tenant_id, team.project_id)
