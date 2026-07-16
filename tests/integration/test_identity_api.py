from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from corvus.application.oauth import OAuthCallback, OAuthStart, VerifiedIdentity
from corvus.infrastructure.db import M1_CURRENT_REVISION, upgrade_database
from corvus.mvp.api import create_app
from corvus.platform.api.dependencies import build_identity_dependencies
from corvus.store import TraceStore

_ORIGIN = "https://corvus.example"
_CALLBACK = f"{_ORIGIN}/api/v2/auth/google/callback"
_SESSION_SECRET = "session-secret-value-that-is-at-least-32-characters"  # noqa: S105


class _OAuthClient:
    def __init__(self) -> None:
        self.exchange_calls: list[OAuthCallback] = []

    def start(self, redirect_uri: str) -> OAuthStart:
        assert redirect_uri == _CALLBACK
        return OAuthStart(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth?state=opaque-state"
        )

    def exchange(self, callback: OAuthCallback) -> VerifiedIdentity:
        self.exchange_calls.append(callback)
        return VerifiedIdentity(
            issuer="https://accounts.google.com",
            subject="google-subject-1",
            email="lucas@example.com",
            email_verified=True,
            display_name="Lucas",
        )


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "corvus.db"
    TraceStore(database).engine.dispose()
    assert upgrade_database(database) == M1_CURRENT_REVISION
    return database


def _configured_client(tmp_path: Path) -> tuple[TestClient, _OAuthClient]:
    database = _database(tmp_path)
    oauth = _OAuthClient()
    dependencies = build_identity_dependencies(
        database=database,
        oauth_client=oauth,
        public_origin=_ORIGIN,
        session_secret=_SESSION_SECRET,
        clock=lambda: datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
    )
    app = create_app(
        database=database,
        bootstrap_token=secrets.token_urlsafe(32),
        session_secret=secrets.token_bytes(48),
        identity_dependencies=dependencies,
    )
    return TestClient(app, base_url=_ORIGIN), oauth


def _login(client: TestClient) -> tuple[str, str, str]:
    response = client.get(
        "/api/v2/auth/google/callback",
        params={"code": "provider-code", "state": "opaque-state"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/onboarding"
    session_cookie = client.cookies.get("__Host-corvus_v2_session")
    device_cookie = client.cookies.get("__Host-corvus_v2_device")
    assert session_cookie is not None
    assert device_cookie is not None
    session = client.get("/api/v2/session")
    assert session.status_code == 200, session.text
    return session.json()["csrf_token"], session_cookie, device_cookie


def _mutation_headers(csrf: str, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Origin": _ORIGIN, "X-CSRF-Token": csrf}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def test_unconfigured_v2_routes_are_discoverable_and_truthfully_unavailable(tmp_path: Path) -> None:
    static = tmp_path / "web"
    static.mkdir()
    (static / "index.html").write_text("<main>Corvus</main>", encoding="utf-8")
    client = TestClient(
        create_app(
            database=tmp_path / "legacy.db",
            bootstrap_token=secrets.token_urlsafe(32),
            session_secret=secrets.token_bytes(48),
            static_web_dir=static,
        )
    )

    response = client.get("/api/v2/auth/google/start", follow_redirects=False)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "platform_identity_unavailable"
    assert client.get("/").text == "<main>Corvus</main>"
    paths = client.app.openapi()["paths"]
    assert "/api/v2/auth/google/start" in paths
    assert "/api/v2/devices" in paths
    assert list(paths).count("/api/v2/session") == 1


def test_google_callback_sets_separate_secure_host_only_cookies_and_clean_redirect(
    tmp_path: Path,
) -> None:
    client, oauth = _configured_client(tmp_path)

    start = client.get("/api/v2/auth/google/start", follow_redirects=False)
    callback = client.get(
        "/api/v2/auth/google/callback?code=provider-code&state=opaque-state",
        follow_redirects=False,
    )

    assert start.status_code == 302
    assert urlparse(start.headers["location"]).netloc == "accounts.google.com"
    assert parse_qs(urlparse(start.headers["location"]).query)["state"] == ["opaque-state"]
    assert callback.status_code == 303
    assert callback.headers["location"] == "/onboarding"
    set_cookie = callback.headers.get_list("set-cookie")
    assert any(
        value.startswith("__Host-corvus_v2_session=")
        and "Secure" in value
        and "HttpOnly" in value
        and "SameSite=lax" in value
        and "Path=/" in value
        and "Domain=" not in value
        for value in set_cookie
    )
    assert any(value.startswith("__Host-corvus_v2_device=") for value in set_cookie)
    assert all("provider-code" not in value and "opaque-state" not in value for value in set_cookie)
    assert oauth.exchange_calls == [OAuthCallback(code="provider-code", state="opaque-state")]


def test_session_onboarding_workspace_and_device_contracts_are_versioned_and_scoped(
    tmp_path: Path,
) -> None:
    client, _oauth = _configured_client(tmp_path)
    csrf, _session_token, _device_token = _login(client)
    session = client.get("/api/v2/session").json()

    missing_origin = client.put(
        "/api/v2/onboarding",
        json={"experience_kind": "developer", "expected_version": session["account_version"]},
        headers={"X-CSRF-Token": csrf},
    )
    cross_origin = client.put(
        "/api/v2/onboarding",
        json={"experience_kind": "developer", "expected_version": session["account_version"]},
        headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
    )
    assert missing_origin.status_code == 403
    assert cross_origin.status_code == 403

    onboarding = client.put(
        "/api/v2/onboarding",
        json={"experience_kind": "developer", "expected_version": session["account_version"]},
        headers=_mutation_headers(csrf),
    )
    assert onboarding.status_code == 200, onboarding.text
    assert onboarding.json()["experience_kind"] == "developer"
    assert onboarding.json()["version"] == session["account_version"] + 1

    workspace_body = {"name": "Lucas workspace", "workspace_kind": "individual"}
    workspace = client.post(
        "/api/v2/workspaces",
        json=workspace_body,
        headers=_mutation_headers(csrf, idempotency_key="workspace-create-1"),
    )
    repeated = client.post(
        "/api/v2/workspaces",
        json=workspace_body,
        headers=_mutation_headers(csrf, idempotency_key="workspace-create-1"),
    )
    assert workspace.status_code == 201, workspace.text
    assert repeated.status_code == 200
    assert repeated.json() == workspace.json()
    workspace_id = workspace.json()["id"]
    assert client.get("/api/v2/workspaces").json() == [workspace.json()]

    patched = client.patch(
        f"/api/v2/workspaces/{workspace_id}",
        json={"name": "Renamed", "expected_version": workspace.json()["version"]},
        headers=_mutation_headers(csrf),
    )
    stale = client.patch(
        f"/api/v2/workspaces/{workspace_id}",
        json={"name": "Stale", "expected_version": workspace.json()["version"]},
        headers=_mutation_headers(csrf),
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == 2
    assert stale.status_code == 409

    public_key_digest = hashlib.sha256(b"named-device-public-key").hexdigest()
    device_body = {"name": "Laptop", "public_key_digest": public_key_digest}
    device = client.post(
        "/api/v2/devices",
        json=device_body,
        headers=_mutation_headers(csrf, idempotency_key="device-create-1"),
    )
    repeated_device = client.post(
        "/api/v2/devices",
        json=device_body,
        headers=_mutation_headers(csrf, idempotency_key="device-create-1"),
    )
    assert device.status_code == 201, device.text
    assert repeated_device.status_code == 200
    assert repeated_device.json() == device.json()
    assert "token" not in device.text.casefold()
    assert len(client.get("/api/v2/devices").json()) == 2

    deleted = client.request(
        "DELETE",
        "/api/v2/devices",
        json={"device_id": device.json()["id"], "expected_version": device.json()["version"]},
        headers=_mutation_headers(csrf),
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "revoked"


def test_refresh_rotates_cookie_rejects_replay_and_logout_clears_server_state(
    tmp_path: Path,
) -> None:
    client, _oauth = _configured_client(tmp_path)
    csrf, original_token, _device = _login(client)

    refresh = client.post("/api/v2/session/refresh", headers=_mutation_headers(csrf))

    assert refresh.status_code == 200, refresh.text
    rotated_token = client.cookies.get("__Host-corvus_v2_session")
    assert rotated_token is not None and rotated_token != original_token
    rotated_csrf = refresh.json()["csrf_token"]
    replay_client = TestClient(client.app, base_url=_ORIGIN)
    replay_client.cookies.set("__Host-corvus_v2_session", original_token)
    replay = replay_client.post(
        "/api/v2/session/refresh",
        headers=_mutation_headers(csrf),
    )
    assert replay.status_code == 401
    assert original_token not in replay.text

    logout = client.post("/api/v2/logout", headers=_mutation_headers(rotated_csrf))
    assert logout.status_code == 204
    assert client.get("/api/v2/session").status_code == 401
    assert any(
        value.startswith("__Host-corvus_v2_session=") and "Max-Age=0" in value
        for value in logout.headers.get_list("set-cookie")
    )


def test_legacy_pairing_auth_remains_independent_from_v2_cookie(tmp_path: Path) -> None:
    client, _oauth = _configured_client(tmp_path)
    _login(client)

    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/auth/session").status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/v2/session",
        "/api/v2/onboarding",
        "/api/v2/workspaces",
        "/api/v2/devices",
    ],
)
def test_unauthenticated_v2_bodies_never_echo_desktop_or_provider_tokens(
    tmp_path: Path,
    path: str,
) -> None:
    client, _oauth = _configured_client(tmp_path)
    canary = "desktop-provider-secret-canary"

    response = client.get(path, params={"token": canary})

    assert response.status_code == 401
    assert canary not in response.text
