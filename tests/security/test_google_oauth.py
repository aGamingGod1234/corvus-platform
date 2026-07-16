from __future__ import annotations

import base64
import hashlib
import sqlite3
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.deprecate import AuthlibDeprecationWarning
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from corvus.application.oauth import OAuthCallback, OAuthError
from corvus.infrastructure.db import M1_CURRENT_REVISION, upgrade_database
from corvus.infrastructure.oauth.google import (
    GOOGLE_AUTHORIZATION_ENDPOINT,
    GOOGLE_JWKS_ENDPOINT,
    GOOGLE_TOKEN_ENDPOINT,
    GoogleOAuthClient,
    GoogleOAuthConfig,
)
from corvus.infrastructure.oauth.repository import OAuthTransactionRepository
from corvus.store import TraceStore

warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)
from authlib.jose import JsonWebKey, jwt  # noqa: E402

_NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
_REDIRECT_URI = "https://corvus.example/api/v2/auth/google/callback"
_CLIENT_ID = "corvus-client.apps.googleusercontent.com"
_CLIENT_SECRET = "google-client-secret-value"  # noqa: S105
_STATE_SECRET = "oauth-state-secret-value-that-is-at-least-32-characters"  # noqa: S105
_TRANSACTION_SECRET = "oauth-transaction-secret-value-at-least-32-characters"  # noqa: S105


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "corvus.db"
    TraceStore(database).engine.dispose()
    assert upgrade_database(database) == M1_CURRENT_REVISION
    return database


class _SecretResolver:
    def resolve(self, reference: str) -> str:
        assert reference == "env://CORVUS_GOOGLE_CLIENT_SECRET"
        return _CLIENT_SECRET


class _Transport:
    def __init__(self, token_response: dict[str, Any], jwks: dict[str, Any]) -> None:
        self.token_response = token_response
        self.jwks = jwks
        self.token_calls: list[tuple[str, dict[str, str]]] = []
        self.jwks_calls: list[str] = []

    def exchange_code(self, endpoint: str, form: dict[str, str]) -> dict[str, Any]:
        self.token_calls.append((endpoint, dict(form)))
        return dict(self.token_response)

    def fetch_jwks(self, endpoint: str) -> dict[str, Any]:
        self.jwks_calls.append(endpoint)
        return self.jwks


def _signing_material() -> tuple[Any, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = JsonWebKey.import_key(public_pem).as_dict()
    public_jwk.update({"kid": "google-key-1", "use": "sig", "alg": "RS256"})
    return private_key, {"keys": [public_jwk]}


def _id_token(private_key: Any, *, nonce: str, **claims: Any) -> str:
    payload: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "sub": "google-subject-1",
        "aud": _CLIENT_ID,
        "azp": _CLIENT_ID,
        "email": "Lucas@Example.com",
        "email_verified": True,
        "name": "Lucas",
        "nonce": nonce,
        "iat": int(_NOW.timestamp()),
        "exp": int((_NOW + timedelta(minutes=5)).timestamp()),
    }
    payload.update(claims)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    encoded = jwt.encode({"alg": "RS256", "kid": "google-key-1"}, payload, private_pem)
    return encoded.decode("ascii") if isinstance(encoded, bytes) else encoded


def _client(
    tmp_path: Path,
    *,
    transport: _Transport | None = None,
) -> tuple[GoogleOAuthClient, OAuthTransactionRepository, _Transport, Any]:
    private_key, jwks = _signing_material()
    selected_transport = transport or _Transport({}, jwks)
    repository = OAuthTransactionRepository(
        _database(tmp_path),
        encryption_secret=_TRANSACTION_SECRET,
    )
    client = GoogleOAuthClient(
        config=GoogleOAuthConfig(
            client_id=_CLIENT_ID,
            client_secret_ref="env://CORVUS_GOOGLE_CLIENT_SECRET",  # noqa: S106
            redirect_uris=frozenset({_REDIRECT_URI}),
            state_secret=_STATE_SECRET,
        ),
        transactions=repository,
        transport=selected_transport,
        secret_resolver=_SecretResolver(),
        clock=lambda: _NOW,
    )
    return client, repository, selected_transport, private_key


def _start_values(client: GoogleOAuthClient) -> tuple[str, str, dict[str, list[str]]]:
    start = client.start(_REDIRECT_URI)
    parsed = urlparse(start.authorization_url)
    values = parse_qs(parsed.query)
    return values["state"][0], values["nonce"][0], values


def test_start_persists_digest_only_transaction_and_emits_s256_pkce(tmp_path: Path) -> None:
    client, _repository, _transport, _private_key = _client(tmp_path)

    state, nonce, values = _start_values(client)

    assert client.authorization_endpoint == GOOGLE_AUTHORIZATION_ENDPOINT
    assert values["redirect_uri"] == [_REDIRECT_URI]
    assert values["response_type"] == ["code"]
    assert values["code_challenge_method"] == ["S256"]
    assert len(base64.urlsafe_b64decode(state + "==")) >= 32
    assert len(base64.urlsafe_b64decode(nonce + "==")) >= 32
    with sqlite3.connect(_database_path(client)) as connection:
        row = connection.execute(
            "SELECT state_digest, nonce_digest, redirect_uri, encrypted_pkce_verifier "
            "FROM oauth_transactions"
        ).fetchone()
        database_bytes = Path(_database_path(client)).read_bytes()
    assert row is not None
    assert row[0] == hashlib.sha256(state.encode()).hexdigest()
    assert row[1] == hashlib.sha256(nonce.encode()).hexdigest()
    assert row[2] == _REDIRECT_URI
    assert state.encode() not in database_bytes
    assert nonce.encode() not in database_bytes
    assert values["code_challenge"][0].encode() not in database_bytes
    assert row[3]


def _database_path(client: GoogleOAuthClient) -> Path:
    return client.transactions.database_path


def test_exchange_resolves_secret_late_and_validates_google_id_token(tmp_path: Path) -> None:
    client, _repository, transport, private_key = _client(tmp_path)
    state, nonce, _values = _start_values(client)
    transport.token_response = {
        "access_token": "provider-access-token",
        "token_type": "Bearer",
        "id_token": _id_token(private_key, nonce=nonce),
    }

    identity = client.exchange(OAuthCallback(code="provider-code", state=state))

    assert identity.subject == "google-subject-1"
    assert identity.email == "Lucas@Example.com"
    assert identity.email_verified is True
    assert transport.jwks_calls == [GOOGLE_JWKS_ENDPOINT]
    endpoint, form = transport.token_calls[0]
    assert endpoint == GOOGLE_TOKEN_ENDPOINT
    assert form["client_secret"] == _CLIENT_SECRET
    assert form["redirect_uri"] == _REDIRECT_URI
    assert form["code"] == "provider-code"
    assert len(form["code_verifier"]) >= 43


@pytest.mark.parametrize(
    ("claim_overrides", "reason"),
    [
        ({"iss": "https://evil.example"}, "google_id_token_issuer_invalid"),
        ({"aud": "other-client"}, "google_id_token_audience_invalid"),
        ({"azp": "other-client"}, "google_id_token_authorized_party_invalid"),
        ({"sub": ""}, "google_id_token_subject_invalid"),
        ({"email_verified": False}, "google_email_unverified"),
        ({"exp": int((_NOW - timedelta(seconds=1)).timestamp())}, "google_id_token_expired"),
    ],
)
def test_exchange_rejects_invalid_google_claims_and_consumes_transaction(
    tmp_path: Path,
    claim_overrides: dict[str, Any],
    reason: str,
) -> None:
    client, repository, transport, private_key = _client(tmp_path)
    state, nonce, _values = _start_values(client)
    transport.token_response = {"id_token": _id_token(private_key, nonce=nonce, **claim_overrides)}

    with pytest.raises(OAuthError, match=reason) as error:
        client.exchange(OAuthCallback(code="provider-code", state=state))

    assert "provider-code" not in str(error.value)
    assert repository.is_consumed(state) is True
    with pytest.raises(OAuthError, match="oauth_transaction_consumed"):
        client.exchange(OAuthCallback(code="provider-code", state=state))


def test_unknown_kid_refreshes_jwks_once_then_fails_redacted(tmp_path: Path) -> None:
    private_key, _jwks = _signing_material()
    transport = _Transport({}, {"keys": []})
    client, repository, _selected, _unused = _client(tmp_path, transport=transport)
    state, nonce, _values = _start_values(client)
    transport.token_response = {"id_token": _id_token(private_key, nonce=nonce)}

    with pytest.raises(OAuthError, match="google_id_token_key_unavailable") as error:
        client.exchange(OAuthCallback(code="secret-code", state=state))

    assert transport.jwks_calls == [GOOGLE_JWKS_ENDPOINT, GOOGLE_JWKS_ENDPOINT]
    assert "secret-code" not in str(error.value)
    assert state not in str(error.value)
    assert repository.is_consumed(state) is True


def test_start_rejects_non_allowlisted_redirect_without_persisting(tmp_path: Path) -> None:
    client, repository, _transport, _private_key = _client(tmp_path)

    with pytest.raises(OAuthError, match="oauth_redirect_uri_forbidden"):
        client.start("https://evil.example/callback")

    assert repository.count() == 0


def test_exchange_rejects_tampered_state_before_transaction_lookup(tmp_path: Path) -> None:
    client, repository, transport, _private_key = _client(tmp_path)
    state, _nonce, _values = _start_values(client)
    tampered_state = f"{state[:-1]}{'A' if state[-1] != 'A' else 'B'}"

    with pytest.raises(OAuthError, match="oauth_state_invalid"):
        client.exchange(OAuthCallback(code="provider-code", state=tampered_state))

    assert transport.token_calls == []
    assert repository.is_consumed(state) is False


def test_expired_transaction_is_durably_consumed(tmp_path: Path) -> None:
    client, repository, _transport, _private_key = _client(tmp_path)
    state, _nonce, _values = _start_values(client)
    expired_at = _NOW + timedelta(minutes=11)

    with pytest.raises(OAuthError, match="oauth_transaction_expired"):
        repository.consume(state=state, now=expired_at)

    assert repository.is_consumed(state) is True
    with pytest.raises(OAuthError, match="oauth_transaction_consumed"):
        repository.consume(state=state, now=expired_at)
