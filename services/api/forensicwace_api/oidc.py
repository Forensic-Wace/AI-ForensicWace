"""OIDC single sign-on (authorization-code flow).

An optional second login method next to local accounts: the API redirects the
browser to the identity provider, exchanges the returned code server-side and
validates the ID token against the provider's JWKS. Successful logins mint the
same ``fw_session`` cookie as password logins; accounts are auto-provisioned
with the ``analyst`` role on first SSO login and promoted locally by an admin.

CSRF protection is the standard double check: the ``state`` parameter is a
short-lived JWT signed with our session secret AND echoed in a SameSite=Lax
cookie, and the ID token's ``nonce`` must match the one embedded in the state.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, Request

from forensicwace_core.config import Settings, get_settings

from .auth import _secret

logger = logging.getLogger(__name__)

STATE_COOKIE = "fw_oidc_state"
STATE_TTL_SECONDS = 600
# asymmetric only: never accept an HMAC alg chosen by the token issuer
ID_TOKEN_ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "ES256", "ES384"]

# injectable for tests (httpx.MockTransport)
_transport: httpx.BaseTransport | None = None


def _client() -> httpx.Client:
    return httpx.Client(transport=_transport, timeout=10)


@lru_cache(maxsize=4)
def _discover(issuer: str) -> dict:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    with _client() as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def clear_discovery_cache() -> None:
    _discover.cache_clear()


def redirect_uri(request: Request) -> str:
    settings = get_settings()
    base = (settings.public_url or str(request.base_url)).rstrip("/")
    return f"{base}/api/v1/auth/oidc/callback"


def authorization_url(request: Request) -> tuple[str, str]:
    """The IdP redirect target and the state token to mirror in a cookie."""
    settings = get_settings()
    meta = _discover(settings.oidc_issuer)
    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {"nonce": nonce, "exp": datetime.now(timezone.utc) + timedelta(seconds=STATE_TTL_SECONDS)},
        _secret(),
        algorithm="HS256",
    )
    params = urlencode(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": redirect_uri(request),
            "scope": settings.oidc_scopes,
            "state": state,
            "nonce": nonce,
        }
    )
    return f"{meta['authorization_endpoint']}?{params}", state


def exchange_code(request: Request, code: str, state: str, cookie_state: str | None) -> dict:
    """Exchange the authorization code and return the validated ID-token claims."""
    settings = get_settings()
    if not cookie_state or not secrets.compare_digest(state, cookie_state):
        raise HTTPException(status_code=400, detail="OIDC state mismatch")
    try:
        state_claims = jwt.decode(state, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="OIDC state expired or invalid")

    meta = _discover(settings.oidc_issuer)
    with _client() as client:
        token_response = client.post(
            meta["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri(request),
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret or "",
            },
        )
        if token_response.status_code != 200:
            logger.warning("OIDC token exchange failed: %s %s", token_response.status_code, token_response.text[:200])
            raise HTTPException(status_code=502, detail="OIDC token exchange failed")
        id_token = token_response.json().get("id_token")
        if not id_token:
            raise HTTPException(status_code=502, detail="Identity provider returned no id_token")
        jwks_response = client.get(meta["jwks_uri"])
        jwks_response.raise_for_status()
        jwks = jwks_response.json()

    claims = _validate_id_token(id_token, jwks, settings)
    if claims.get("nonce") != state_claims["nonce"]:
        raise HTTPException(status_code=400, detail="OIDC nonce mismatch")
    return claims


def _validate_id_token(id_token: str, jwks: dict, settings: Settings) -> dict:
    header = jwt.get_unverified_header(id_token)
    keys = jwks.get("keys", [])
    entry = next((k for k in keys if k.get("kid") == header.get("kid")), None)
    if entry is None and len(keys) == 1:  # some IdPs omit kid on single-key sets
        entry = keys[0]
    if entry is None:
        raise HTTPException(status_code=502, detail="No matching key in the provider JWKS")
    try:
        return jwt.decode(
            id_token,
            key=jwt.PyJWK(entry).key,
            algorithms=ID_TOKEN_ALGORITHMS,
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer.rstrip("/"),
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid ID token: {exc}")
