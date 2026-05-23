"""FastMCP server exposing read-only secforms tools over Streamable HTTP."""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from .config import settings
from .db import close_pool, healthy, init_pool
from .guard import validate as guard_validate
from .oauth import (
    authorize_get, authorize_post, register, token as oauth_token,
    validate_jwt, well_known_authorization_server, well_known_protected_resource,
)
from .tools import query as q_tools
from .tools import schema as s_tools


logging.basicConfig(
    level=settings.log_level.upper(),
    stream=sys.stdout,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
)
log = logging.getLogger("secforms-mcp")


mcp = FastMCP(
    name="secforms-db",
    instructions=(
        "Read-only access to the secforms (SEC filings) Postgres database. "
        "Use `query` for SELECT/WITH/EXPLAIN statements. Use `list_tables`, "
        "`describe_table`, `list_foreign_keys`, `schema_summary` for introspection. "
        "Mutation tools are not provided. The DB role is also read-only."
    ),
)


@mcp.tool()
async def query(sql: str, params: list[Any] | None = None, limit: int | None = None) -> dict[str, Any]:
    """Run a SELECT / WITH SELECT / EXPLAIN statement. Returns rows + metadata.

    Args:
        sql: One SQL statement. Only SELECT, WITH ... SELECT, and EXPLAIN SELECT are allowed.
        params: Positional parameter values for $1, $2, ... placeholders.
        limit: Row cap. Defaults to 100. Max 10000. Ignored if SQL already has a LIMIT.
    """
    return await q_tools.query(sql, params, limit)


@mcp.tool()
async def count(table: str, where: str | None = None, params: list[Any] | None = None) -> dict[str, Any]:
    """SELECT COUNT(*) on a table, optionally filtered by a WHERE clause."""
    return await q_tools.count(table, where, params)


@mcp.tool()
async def explain(sql: str, params: list[Any] | None = None) -> dict[str, Any]:
    """EXPLAIN (FORMAT JSON) for a SELECT. Does not execute the query."""
    return await q_tools.explain(sql, params)


@mcp.tool()
async def list_tables(schema: str = "public") -> dict[str, Any]:
    """List base tables in a schema."""
    return await s_tools.list_tables(schema)


@mcp.tool()
async def describe_table(name: str, schema: str = "public") -> dict[str, Any]:
    """Columns + types + PK + FKs for one table."""
    return await s_tools.describe_table(name, schema)


@mcp.tool()
async def list_foreign_keys() -> dict[str, Any]:
    """All FK edges across allowed schemas (join discovery)."""
    return await s_tools.list_foreign_keys()


@mcp.tool()
async def schema_summary() -> dict[str, Any]:
    """One-shot summary: schemas, table count, FK count, per-table column counts."""
    return await s_tools.schema_summary()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip", "")
    if real:
        return real.strip()
    return request.client.host if request.client else ""


PUBLIC_PATHS = (
    "/healthz",
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-authorization-server",
    "/oauth/authorize",
    "/oauth/token",
    "/oauth/register",
)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in PUBLIC_PATHS):
            return await call_next(request)

        token_map = settings.token_map
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return _unauthorized_with_challenge()

        client_ip = _client_ip(request)

        # 1. Try as JWT (OAuth issued)
        claims = validate_jwt(token)
        if claims is not None:
            name = claims.get("invite_name") or claims.get("sub") or "oauth"
            entry = next((e for e in settings.token_entries if e.name == name), None)
            if entry is not None and not entry.matches_ip(client_ip):
                log.warning(json.dumps({"event": "ip_denied", "name": name, "client_ip": client_ip}))
                return JSONResponse({"error": "Forbidden: source IP not allowed for this identity."}, status_code=403)
            request.state.token_id = hashlib.sha256(token.encode()).hexdigest()[:12]
            request.state.token_name = name
            request.state.auth_kind = "jwt"
            request.state.client_ip = client_ip
            request.state.request_id = str(uuid.uuid4())
            return await call_next(request)

        # 2. Try as static invite token (legacy path: curl scripts, internal jobs)
        entry = token_map.get(token)
        if entry is None:
            return _unauthorized_with_challenge()
        if not entry.matches_ip(client_ip):
            log.warning(json.dumps({"event": "ip_denied", "name": entry.name, "client_ip": client_ip}))
            return JSONResponse({"error": "Forbidden: source IP not allowed for this token."}, status_code=403)

        request.state.token_id = hashlib.sha256(token.encode()).hexdigest()[:12]
        request.state.token_name = entry.name
        request.state.auth_kind = "static"
        request.state.client_ip = client_ip
        request.state.request_id = str(uuid.uuid4())
        return await call_next(request)


def _unauthorized_with_challenge() -> JSONResponse:
    challenge = (
        f'Bearer realm="secforms-db", '
        f'resource_metadata="{settings.public_base_url}/.well-known/oauth-protected-resource"'
    )
    return JSONResponse(
        {"error": "Unauthorized"},
        status_code=401,
        headers={"WWW-Authenticate": challenge},
    )


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        rec = {
            "request_id": getattr(request.state, "request_id", None),
            "token_id": getattr(request.state, "token_id", None),
            "name": getattr(request.state, "token_name", None),
            "client_ip": getattr(request.state, "client_ip", None),
            "method": request.method,
            "path": request.url.path,
            "status": resp.status_code,
        }
        log.info(json.dumps(rec))
        return resp


async def healthz(_: Request) -> Response:
    ok = await healthy()
    return JSONResponse({"status": "ok" if ok else "degraded"}, status_code=200 if ok else 503)


def build_app() -> Starlette:
    mcp_app = mcp.http_app(path="/mcp")

    @asynccontextmanager
    async def lifespan(app: Starlette):
        await init_pool()
        try:
            async with mcp_app.router.lifespan_context(app):
                yield
        finally:
            await close_pool()

    return Starlette(
        debug=False,
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Route("/.well-known/oauth-protected-resource",
                  well_known_protected_resource, methods=["GET"]),
            Route("/.well-known/oauth-authorization-server",
                  well_known_authorization_server, methods=["GET"]),
            Route("/oauth/register", register, methods=["POST"]),
            Route("/oauth/authorize", authorize_get, methods=["GET"]),
            Route("/oauth/authorize", authorize_post, methods=["POST"]),
            Route("/oauth/token", oauth_token, methods=["POST"]),
            Mount("/", app=mcp_app),
        ],
        middleware=[
            Middleware(BearerAuthMiddleware),
            Middleware(RequestLogMiddleware),
        ],
        lifespan=lifespan,
    )


app = build_app()
