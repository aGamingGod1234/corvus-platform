import hmac
from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from corvus.application.oauth import OAuthCallback, OAuthError
from corvus.domain.account import DeviceRegistration, ExperienceKind, normalize_identity_email
from corvus.domain.identity import Workspace, WorkspaceKind
from corvus.infrastructure.repositories.accounts import (
    AccountRepositoryError,
    WebSessionAuthentication,
)
from corvus.infrastructure.repositories.platform_identity import PlatformIdentityRepositoryError
from corvus.platform.api.dependencies import IdentityApiDependencies

_SESSION_COOKIE = "__Host-corvus_v2_session"
_DEVICE_COOKIE = "__Host-corvus_v2_device"
_SESSION_TTL = timedelta(days=30)
_CALLBACK_PATH = "/api/v2/auth/google/callback"
_ONBOARDING_DESTINATION = "/onboarding"


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OnboardingUpdate(ApiModel):
    experience_kind: ExperienceKind
    expected_version: int = Field(ge=1)


class WorkspaceCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    workspace_kind: WorkspaceKind


class WorkspaceUpdate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)


class DeviceCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    public_key_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class DeviceDelete(ApiModel):
    device_id: UUID
    expected_version: int = Field(ge=1)


def _error(code: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "correlation_id": str(uuid4())},
    )


def _map_error(error: Exception) -> HTTPException:
    code = str(error)
    if code.endswith("_conflict") or code == "idempotency_payload_mismatch":
        return _error(code, status.HTTP_409_CONFLICT)
    if code.endswith("not_found"):
        return _error(code, status.HTTP_404_NOT_FOUND)
    if code.endswith("forbidden"):
        return _error(code, status.HTTP_403_FORBIDDEN)
    if code.startswith("session_"):
        return _error("session_invalid", status.HTTP_401_UNAUTHORIZED)
    if code.startswith("oauth_") or code.startswith("google_"):
        return _error(code, status.HTTP_400_BAD_REQUEST)
    return _error("platform_identity_failure", status.HTTP_503_SERVICE_UNAVAILABLE)


def _set_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        key=name,
        value=value,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _clear_cookie(response: Response, name: str) -> None:
    response.delete_cookie(
        key=name,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _workspace_payload(workspace: Workspace) -> dict[str, object]:
    return workspace.model_dump(mode="json")


def _device_payload(device: DeviceRegistration) -> dict[str, object]:
    return device.model_dump(mode="json")


def create_identity_router(dependencies: IdentityApiDependencies | None) -> APIRouter:
    router = APIRouter(prefix="/api/v2", tags=["platform-identity"])
    if dependencies is None:

        def unavailable() -> None:
            raise _error("platform_identity_unavailable", status.HTTP_503_SERVICE_UNAVAILABLE)

        routes = (
            ("/auth/google/start", "GET", "unavailable_google_start"),
            ("/auth/google/callback", "GET", "unavailable_google_callback"),
            ("/session", "GET", "unavailable_session"),
            ("/session/refresh", "POST", "unavailable_session_refresh"),
            ("/logout", "POST", "unavailable_logout"),
            ("/onboarding", "GET", "unavailable_onboarding_get"),
            ("/onboarding", "PUT", "unavailable_onboarding_put"),
            ("/workspaces", "GET", "unavailable_workspaces_get"),
            ("/workspaces", "POST", "unavailable_workspaces_post"),
            ("/workspaces/{workspace_id}", "GET", "unavailable_workspace_get"),
            ("/workspaces/{workspace_id}", "PATCH", "unavailable_workspace_patch"),
            ("/devices", "GET", "unavailable_devices_get"),
            ("/devices", "POST", "unavailable_devices_post"),
            ("/devices", "DELETE", "unavailable_devices_delete"),
        )
        for path, method, operation_id in routes:
            router.add_api_route(
                path,
                unavailable,
                methods=[method],
                operation_id=operation_id,
            )
        return router

    def authenticated(
        session_token: Annotated[str | None, Cookie(alias=_SESSION_COOKIE)] = None,
    ) -> WebSessionAuthentication:
        if session_token is None:
            raise _error("session_required", status.HTTP_401_UNAUTHORIZED)
        try:
            return dependencies.accounts.authenticate_web_session(
                session_token=session_token,
                session_secret=dependencies.session_secret,
                now=dependencies.clock(),
            )
        except AccountRepositoryError as exc:
            raise _map_error(exc) from None

    def mutation_authenticated(
        request: Request,
        session: Annotated[WebSessionAuthentication, Depends(authenticated)],
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> WebSessionAuthentication:
        if request.headers.get("origin") != dependencies.public_origin:
            raise _error("origin_forbidden", status.HTTP_403_FORBIDDEN)
        if csrf_token is None or not hmac.compare_digest(csrf_token, session.csrf_token):
            raise _error("csrf_invalid", status.HTTP_403_FORBIDDEN)
        return session

    @router.get("/auth/google/start", status_code=302)
    def google_start() -> RedirectResponse:
        try:
            result = dependencies.oauth_client.start(
                f"{dependencies.public_origin}{_CALLBACK_PATH}"
            )
        except (OAuthError, ValueError) as exc:
            raise _map_error(exc) from None
        return RedirectResponse(result.authorization_url, status_code=status.HTTP_302_FOUND)

    @router.get("/auth/google/callback")
    def google_callback(
        code: Annotated[str | None, Query()] = None,
        state_value: Annotated[str | None, Query(alias="state")] = None,
        device_token: Annotated[str | None, Cookie(alias=_DEVICE_COOKIE)] = None,
    ) -> RedirectResponse:
        if (
            code is None
            or state_value is None
            or not 1 <= len(code) <= 4096
            or not 1 <= len(state_value) <= 4096
        ):
            raise _error("oauth_callback_invalid", status.HTTP_400_BAD_REQUEST)
        try:
            identity = dependencies.oauth_client.exchange(
                OAuthCallback(code=code, state=state_value)
            )
            now = dependencies.clock()
            login = dependencies.accounts.complete_web_login(
                issuer=identity.issuer,
                subject=identity.subject,
                normalized_email=normalize_identity_email(identity.email),
                display_name=identity.display_name,
                existing_device_token=device_token,
                session_secret=dependencies.session_secret,
                now=now,
                expires_at=now + _SESSION_TTL,
            )
        except (OAuthError, AccountRepositoryError, ValueError) as exc:
            raise _map_error(exc) from None
        response = RedirectResponse(
            _ONBOARDING_DESTINATION,
            status_code=status.HTTP_303_SEE_OTHER,
        )
        _set_cookie(response, _SESSION_COOKIE, login.session_token)
        if login.device_token is not None:
            _set_cookie(response, _DEVICE_COOKIE, login.device_token)
        return response

    @router.get("/session")
    def session(
        authenticated_session: Annotated[WebSessionAuthentication, Depends(authenticated)],
    ) -> dict[str, object]:
        experience, account_version = dependencies.platform.get_onboarding(
            authenticated_session.account.id
        )
        return {
            "account_id": str(authenticated_session.account.id),
            "principal_id": str(authenticated_session.account.principal_id),
            "email": authenticated_session.account.normalized_email,
            "experience_kind": None if experience is None else experience.value,
            "account_version": account_version,
            "session_version": authenticated_session.session.version,
            "csrf_token": authenticated_session.csrf_token,
        }

    @router.post("/session/refresh")
    def refresh_session(
        _authenticated: Annotated[WebSessionAuthentication, Depends(mutation_authenticated)],
        response: Response,
        session_token: Annotated[str | None, Cookie(alias=_SESSION_COOKIE)] = None,
    ) -> dict[str, object]:
        if session_token is None:
            raise _error("session_required", status.HTTP_401_UNAUTHORIZED)
        try:
            now = dependencies.clock()
            rotated = dependencies.accounts.rotate_web_session(
                session_token=session_token,
                session_secret=dependencies.session_secret,
                now=now,
                expires_at=now + _SESSION_TTL,
            )
        except AccountRepositoryError as exc:
            raise _map_error(exc) from None
        _set_cookie(response, _SESSION_COOKIE, rotated.session_token)
        return {"csrf_token": rotated.csrf_token, "session_version": rotated.session.version}

    @router.post("/logout", status_code=204)
    def logout(
        _authenticated: Annotated[WebSessionAuthentication, Depends(mutation_authenticated)],
        response: Response,
        session_token: Annotated[str | None, Cookie(alias=_SESSION_COOKIE)] = None,
    ) -> Response:
        if session_token is None:
            raise _error("session_required", status.HTTP_401_UNAUTHORIZED)
        try:
            dependencies.accounts.revoke_web_session(
                session_token=session_token,
                session_secret=dependencies.session_secret,
                now=dependencies.clock(),
            )
        except AccountRepositoryError as exc:
            raise _map_error(exc) from None
        _clear_cookie(response, _SESSION_COOKIE)
        response.status_code = status.HTTP_204_NO_CONTENT
        return response

    @router.get("/onboarding")
    def get_onboarding(
        session: Annotated[WebSessionAuthentication, Depends(authenticated)],
    ) -> dict[str, object]:
        experience, version = dependencies.platform.get_onboarding(session.account.id)
        return {
            "experience_kind": None if experience is None else experience.value,
            "version": version,
        }

    @router.put("/onboarding")
    def update_onboarding(
        body: OnboardingUpdate,
        session: Annotated[WebSessionAuthentication, Depends(mutation_authenticated)],
    ) -> dict[str, object]:
        try:
            experience, version = dependencies.platform.update_onboarding(
                account_id=session.account.id,
                experience_kind=body.experience_kind,
                expected_version=body.expected_version,
                now=dependencies.clock(),
            )
        except PlatformIdentityRepositoryError as exc:
            raise _map_error(exc) from None
        return {"experience_kind": experience.value, "version": version}

    @router.get("/workspaces")
    def list_workspaces(
        session: Annotated[WebSessionAuthentication, Depends(authenticated)],
    ) -> list[dict[str, object]]:
        return [
            _workspace_payload(workspace)
            for workspace in dependencies.platform.list_workspaces(session.account.principal_id)
        ]

    @router.post("/workspaces")
    def create_workspace(
        body: WorkspaceCreate,
        session: Annotated[WebSessionAuthentication, Depends(mutation_authenticated)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    ) -> JSONResponse:
        try:
            workspace, repeated = dependencies.platform.create_workspace(
                account_id=session.account.id,
                principal_id=session.account.principal_id,
                name=body.name,
                workspace_kind=body.workspace_kind,
                idempotency_key=idempotency_key,
                now=dependencies.clock(),
            )
        except PlatformIdentityRepositoryError as exc:
            raise _map_error(exc) from None
        return JSONResponse(
            _workspace_payload(workspace),
            status_code=status.HTTP_200_OK if repeated else status.HTTP_201_CREATED,
        )

    @router.get("/workspaces/{workspace_id}")
    def get_workspace(
        workspace_id: UUID,
        session: Annotated[WebSessionAuthentication, Depends(authenticated)],
    ) -> dict[str, object]:
        matches = {
            workspace.id: workspace
            for workspace in dependencies.platform.list_workspaces(session.account.principal_id)
        }
        workspace = matches.get(workspace_id)
        if workspace is None:
            raise _error("workspace_not_found", status.HTTP_404_NOT_FOUND)
        return _workspace_payload(workspace)

    @router.patch("/workspaces/{workspace_id}")
    def update_workspace(
        workspace_id: UUID,
        body: WorkspaceUpdate,
        session: Annotated[WebSessionAuthentication, Depends(mutation_authenticated)],
    ) -> dict[str, object]:
        try:
            workspace = dependencies.platform.update_workspace(
                principal_id=session.account.principal_id,
                workspace_id=workspace_id,
                name=body.name,
                expected_version=body.expected_version,
                now=dependencies.clock(),
            )
        except PlatformIdentityRepositoryError as exc:
            raise _map_error(exc) from None
        return _workspace_payload(workspace)

    @router.get("/devices")
    def list_devices(
        session: Annotated[WebSessionAuthentication, Depends(authenticated)],
    ) -> list[dict[str, object]]:
        return [
            _device_payload(device)
            for device in dependencies.platform.list_devices(session.account.id)
        ]

    @router.post("/devices")
    def create_device(
        body: DeviceCreate,
        session: Annotated[WebSessionAuthentication, Depends(mutation_authenticated)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    ) -> JSONResponse:
        try:
            device, repeated = dependencies.platform.register_device(
                account_id=session.account.id,
                name=body.name,
                public_key_digest=body.public_key_digest,
                idempotency_key=idempotency_key,
                now=dependencies.clock(),
            )
        except PlatformIdentityRepositoryError as exc:
            raise _map_error(exc) from None
        return JSONResponse(
            _device_payload(device),
            status_code=status.HTTP_200_OK if repeated else status.HTTP_201_CREATED,
        )

    @router.delete("/devices")
    def delete_device(
        body: DeviceDelete,
        session: Annotated[WebSessionAuthentication, Depends(mutation_authenticated)],
    ) -> dict[str, object]:
        try:
            device = dependencies.platform.revoke_device(
                account_id=session.account.id,
                device_id=body.device_id,
                expected_version=body.expected_version,
                now=dependencies.clock(),
            )
        except PlatformIdentityRepositoryError as exc:
            raise _map_error(exc) from None
        return _device_payload(device)

    return router
