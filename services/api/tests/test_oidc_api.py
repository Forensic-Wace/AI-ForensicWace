"""OIDC single sign-on against a fake identity provider (httpx.MockTransport)."""

import json
import time
from urllib.parse import parse_qs, urlparse

import pytest

fastapi = pytest.importorskip("fastapi")
import httpx  # noqa: E402
import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.analysis import registry  # noqa: E402
from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine  # noqa: E402

ISSUER = "https://idp.test"
CLIENT_ID = "forensicwace"

RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeIdP:
    """Just enough OIDC: discovery, JWKS, token endpoint signing RS256."""

    def __init__(self):
        self.expected_nonce: str | None = None
        self.claim_overrides: dict = {}
        self.token_requests: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                },
            )
        if path == "/jwks":
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(RSA_KEY.public_key()))
            jwk["kid"] = "test-key"
            return httpx.Response(200, json={"keys": [jwk]})
        if path == "/token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            self.token_requests.append(form)
            claims = {
                "iss": ISSUER,
                "aud": CLIENT_ID,
                "sub": "u-123",
                "preferred_username": "ada.sso",
                "name": "Ada Lovelace",
                "exp": int(time.time()) + 300,
                "nonce": self.expected_nonce,
                **self.claim_overrides,
            }
            id_token = jwt.encode(claims, RSA_KEY, algorithm="RS256", headers={"kid": "test-key"})
            return httpx.Response(200, json={"access_token": "at", "token_type": "Bearer", "id_token": id_token})
        return httpx.Response(404)


def _reset_runtime():
    clear_settings_cache()
    registry.clear_registry_cache()
    dispose_engine()


@pytest.fixture
def idp():
    return FakeIdP()


@pytest.fixture
def client(tmp_path, monkeypatch, idp):
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.delenv("FW_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("FW_JWT_SECRET", "test-secret-not-for-production-0123456789")
    monkeypatch.setenv("FW_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("FW_ADMIN_PASSWORD", "correct-horse-battery")
    monkeypatch.setenv("FW_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("FW_OIDC_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("FW_OIDC_CLIENT_SECRET", "s3cret")
    _reset_runtime()

    from forensicwace_api import oidc

    monkeypatch.setattr(oidc, "_transport", httpx.MockTransport(idp.handler))
    oidc.clear_discovery_cache()

    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    oidc.clear_discovery_cache()
    _reset_runtime()


def start_flow(client, idp) -> str:
    """Follow /oidc/login and return the state to send back to the callback."""
    response = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 307
    location = urlparse(response.headers["location"])
    query = {k: v[0] for k, v in parse_qs(location.query).items()}
    assert f"{location.scheme}://{location.netloc}{location.path}" == f"{ISSUER}/authorize"
    assert query["client_id"] == CLIENT_ID
    idp.expected_nonce = query["nonce"]
    return query["state"]


def test_providers_advertises_sso(client):
    assert client.get("/api/v1/auth/providers").json() == {"password": True, "oidc": True}


def test_full_flow_provisions_an_analyst(client, idp):
    state = start_flow(client, idp)
    callback = client.get(f"/api/v1/auth/oidc/callback?code=abc&state={state}", follow_redirects=False)
    assert callback.status_code == 303, callback.text
    assert callback.headers["location"] == "/"

    me = client.get("/api/v1/auth/me").json()
    assert me["username"] == "ada.sso" and me["role"] == "analyst"
    # the secret went to the IdP, not the browser
    assert idp.token_requests[0]["client_secret"] == "s3cret"

    # second SSO login reuses the account
    state = start_flow(client, idp)
    client.get(f"/api/v1/auth/oidc/callback?code=xyz&state={state}", follow_redirects=False)
    client.cookies.clear()
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "correct-horse-battery"}
    ).status_code == 200
    users = client.get("/api/v1/users").json()
    assert [u["username"] for u in users if u["username"] == "ada.sso"] == ["ada.sso"]

    # SSO-only accounts have no password to log in with
    client.cookies.clear()
    assert client.post(
        "/api/v1/auth/login", json={"username": "ada.sso", "password": "anything-at-all"}
    ).status_code == 401


def test_forged_state_is_rejected(client, idp):
    start_flow(client, idp)
    forged = jwt.encode(
        {"nonce": "evil", "exp": int(time.time()) + 600}, "the-wrong-signing-secret-0123456789ab", algorithm="HS256"
    )
    response = client.get(f"/api/v1/auth/oidc/callback?code=abc&state={forged}", follow_redirects=False)
    assert response.status_code == 400
    assert client.get("/api/v1/auth/me").status_code == 401


def test_wrong_audience_is_rejected(client, idp):
    state = start_flow(client, idp)
    idp.claim_overrides = {"aud": "someone-else"}
    response = client.get(f"/api/v1/auth/oidc/callback?code=abc&state={state}", follow_redirects=False)
    assert response.status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
