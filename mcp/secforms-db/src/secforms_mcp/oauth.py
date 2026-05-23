"""OAuth 2.1 layer for the secforms-db MCP.

Spec: MCP 2025-06-18 + OAuth 2.1 (auth code with PKCE).
Identity model: friends present their pre-issued invite code (== one of the static tokens
from TOKENS_JSON) on the authorize page. The server exchanges that for an authorization
code, then for a JWT access token signed with JWT_SECRET. The same TokenEntry identity
flows through (name + ip_allow).

Endpoints exposed:
  GET  /.well-known/oauth-protected-resource     (RFC 9728)
  GET  /.well-known/oauth-authorization-server   (RFC 8414)
  POST /oauth/register                            (RFC 7591 DCR)
  GET  /oauth/authorize                           (auth code form)
  POST /oauth/authorize                           (invite-code submission)
  POST /oauth/token                               (code -> JWT)
"""
from __future__ import annotations

import hashlib
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import jwt
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .config import settings


@dataclass
class PendingAuth:
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    scope: str
    state: str
    invite_name: str
    invite_token: str
    created_at: float = field(default_factory=time.time)


# In-memory stores. Restart-clears. Fine for friends-only.
_codes: dict[str, PendingAuth] = {}
_clients: dict[str, dict[str, Any]] = {}


def _purge_expired() -> None:
    now = time.time()
    for code, p in list(_codes.items()):
        if now - p.created_at > settings.auth_code_ttl_seconds:
            _codes.pop(code, None)


def _check_pkce(verifier: str, challenge: str, method: str) -> bool:
    if method.upper() == "S256":
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        import base64
        derived = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return secrets.compare_digest(derived, challenge)
    return False


def _lookup_invite(invite: str) -> tuple[str, str] | None:
    invite = (invite or "").strip()
    if not invite:
        return None
    for entry in settings.token_entries:
        if secrets.compare_digest(entry.token, invite):
            return entry.name, entry.token
    return None


def metadata_protected_resource() -> dict[str, Any]:
    return {
        "resource": f"{settings.public_base_url}/mcp",
        "authorization_servers": [settings.public_base_url],
        "scopes_supported": ["read:database"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{settings.public_base_url}/",
    }


def metadata_authorization_server() -> dict[str, Any]:
    return {
        "issuer": settings.jwt_issuer,
        "authorization_endpoint": f"{settings.public_base_url}/oauth/authorize",
        "token_endpoint": f"{settings.public_base_url}/oauth/token",
        "registration_endpoint": f"{settings.public_base_url}/oauth/register",
        "scopes_supported": ["read:database"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
    }


async def well_known_protected_resource(_: Request) -> Response:
    return JSONResponse(metadata_protected_resource())


async def well_known_authorization_server(_: Request) -> Response:
    return JSONResponse(metadata_authorization_server())


async def register(request: Request) -> Response:
    body = await request.json() if (await request.body()) else {}
    client_id = "client_" + secrets.token_urlsafe(16)
    record = {
        "client_id": client_id,
        "client_id_issued_at": int(time.time()),
        "client_name": body.get("client_name", "unknown"),
        "redirect_uris": body.get("redirect_uris", []),
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    _clients[client_id] = record
    return JSONResponse(record, status_code=201)


_LOGIN_FORM = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>secforms-db login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:-apple-system,Segoe UI,system-ui,sans-serif;background:#0b0d10;color:#e7e9ec;display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#14171c;padding:32px 36px;border-radius:14px;width:min(420px,92vw);box-shadow:0 24px 60px rgba(0,0,0,.35);border:1px solid #1f242c}}
h1{{margin:0 0 6px;font-size:20px}}
p{{margin:0 0 18px;color:#9aa3ad;font-size:14px;line-height:1.45}}
label{{display:block;font-size:13px;color:#c1c8d1;margin-bottom:6px}}
input{{width:100%;box-sizing:border-box;background:#0b0d10;border:1px solid #2a313a;color:#e7e9ec;padding:11px 13px;border-radius:9px;font-size:14px;font-family:ui-monospace,Menlo,Consolas,monospace}}
input:focus{{outline:none;border-color:#4c8bf5}}
button{{margin-top:18px;width:100%;background:#4c8bf5;color:white;border:0;padding:12px;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer}}
button:hover{{background:#5b97f8}}
.err{{margin-top:14px;color:#ff7a7a;font-size:13px}}
.foot{{margin-top:18px;color:#6b7480;font-size:12px;text-align:center}}
code{{background:#0b0d10;padding:2px 5px;border-radius:4px;color:#9ec5fe}}
</style></head><body>
<form class="card" method="post" action="/oauth/authorize">
<h1>Connect to secforms-db</h1>
<p>Paste the invite code your maintainer sent you. You only need to do this once.</p>
<input type="hidden" name="client_id" value="{client_id}">
<input type="hidden" name="redirect_uri" value="{redirect_uri}">
<input type="hidden" name="state" value="{state}">
<input type="hidden" name="code_challenge" value="{code_challenge}">
<input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
<input type="hidden" name="scope" value="{scope}">
<label for="invite">Invite code</label>
<input id="invite" name="invite" type="password" autocomplete="off" autofocus placeholder="paste your invite code">
<button type="submit">Authorize</button>
{error_block}
<div class="foot">Read-only. Scope: <code>read:database</code></div>
</form></body></html>"""


def _escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def _render_form(params: dict[str, str], error: str = "") -> HTMLResponse:
    err_block = f'<div class="err">{_escape(error)}</div>' if error else ""
    html = _LOGIN_FORM.format(
        client_id=_escape(params.get("client_id", "")),
        redirect_uri=_escape(params.get("redirect_uri", "")),
        state=_escape(params.get("state", "")),
        code_challenge=_escape(params.get("code_challenge", "")),
        code_challenge_method=_escape(params.get("code_challenge_method", "S256")),
        scope=_escape(params.get("scope", "read:database")),
        error_block=err_block,
    )
    return HTMLResponse(html)


async def authorize_get(request: Request) -> Response:
    q = dict(request.query_params)
    required = ["response_type", "client_id", "redirect_uri", "code_challenge", "code_challenge_method"]
    missing = [k for k in required if not q.get(k)]
    if missing:
        return JSONResponse({"error": "invalid_request", "missing": missing}, status_code=400)
    if q["response_type"] != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)
    if q["code_challenge_method"].upper() != "S256":
        return JSONResponse({"error": "invalid_request", "reason": "S256 only"}, status_code=400)
    return _render_form(q)


async def authorize_post(request: Request) -> Response:
    form = await request.form()
    params = {k: form.get(k, "") for k in
              ("client_id", "redirect_uri", "state", "code_challenge",
               "code_challenge_method", "scope", "invite")}
    invite = _lookup_invite(params["invite"])
    if invite is None:
        return _render_form(params, error="Invite code not recognized. Check the code or ask your maintainer.")

    code = secrets.token_urlsafe(32)
    _purge_expired()
    _codes[code] = PendingAuth(
        client_id=params["client_id"],
        redirect_uri=params["redirect_uri"],
        code_challenge=params["code_challenge"],
        code_challenge_method=params["code_challenge_method"] or "S256",
        scope=params["scope"] or "read:database",
        state=params["state"],
        invite_name=invite[0],
        invite_token=invite[1],
    )

    qs = urllib.parse.urlencode({"code": code, "state": params["state"]})
    sep = "&" if "?" in params["redirect_uri"] else "?"
    return RedirectResponse(params["redirect_uri"] + sep + qs, status_code=303)


async def token(request: Request) -> Response:
    if not settings.jwt_secret:
        return JSONResponse({"error": "server_error", "reason": "JWT_SECRET not configured"}, status_code=500)

    form = await request.form()
    grant_type = form.get("grant_type")
    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    code = form.get("code") or ""
    verifier = form.get("code_verifier") or ""
    client_id = form.get("client_id") or ""
    redirect_uri = form.get("redirect_uri") or ""

    pending = _codes.pop(code, None)
    if pending is None:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    if time.time() - pending.created_at > settings.auth_code_ttl_seconds:
        return JSONResponse({"error": "invalid_grant", "reason": "expired"}, status_code=400)
    if client_id and client_id != pending.client_id:
        return JSONResponse({"error": "invalid_grant", "reason": "client mismatch"}, status_code=400)
    if redirect_uri and redirect_uri != pending.redirect_uri:
        return JSONResponse({"error": "invalid_grant", "reason": "redirect mismatch"}, status_code=400)
    if not _check_pkce(verifier, pending.code_challenge, pending.code_challenge_method):
        return JSONResponse({"error": "invalid_grant", "reason": "PKCE failed"}, status_code=400)

    now = int(time.time())
    claims = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": pending.invite_name,
        "scope": pending.scope,
        "iat": now,
        "exp": now + settings.access_token_ttl_seconds,
        "client_id": pending.client_id,
        "invite_name": pending.invite_name,
    }
    access_token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")

    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_ttl_seconds,
        "scope": pending.scope,
    })


def validate_jwt(token_str: str) -> dict[str, Any] | None:
    if not settings.jwt_secret:
        return None
    try:
        return jwt.decode(
            token_str,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError:
        return None
