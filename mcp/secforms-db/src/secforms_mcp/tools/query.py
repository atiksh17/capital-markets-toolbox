"""query / count / explain tools."""
from __future__ import annotations

import json
from typing import Any

from ..config import settings
from ..db import acquire
from ..guard import validate


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return str(value)


async def query(sql: str, params: list[Any] | None = None, limit: int | None = None) -> dict[str, Any]:
    """Run a SELECT / WITH / EXPLAIN. Returns {rows, row_count, columns, truncated, limit}."""
    params = params or []
    limit = min(limit or settings.default_limit, settings.max_limit)

    guard = validate(sql)
    if not guard.ok:
        return {"error": guard.reason, "statement_kind": guard.statement_kind}

    wrapped = _apply_limit(sql, limit)

    async with acquire() as conn:
        rows = await conn.fetch(wrapped, *params)

    columns = list(rows[0].keys()) if rows else []
    out = [{k: _serialize(v) for k, v in r.items()} for r in rows]
    truncated = len(out) >= limit
    return {
        "rows": out,
        "row_count": len(out),
        "columns": columns,
        "truncated": truncated,
        "limit": limit,
    }


async def count(table: str, where: str | None = None, params: list[Any] | None = None) -> dict[str, Any]:
    """SELECT COUNT(*) shortcut. `table` is validated against the schema allowlist."""
    params = params or []
    schema, name = _parse_qualified(table)
    if schema not in settings.schema_set:
        return {"error": f"Schema {schema!r} not allowed."}

    sql = f'SELECT COUNT(*) AS n FROM "{schema}"."{name}"'
    if where:
        where_check = validate(f"SELECT 1 FROM x WHERE {where}")
        if not where_check.ok:
            return {"error": f"WHERE clause rejected: {where_check.reason}"}
        sql += f" WHERE {where}"

    async with acquire() as conn:
        n = await conn.fetchval(sql, *params)
    return {"count": int(n)}


async def explain(sql: str, params: list[Any] | None = None) -> dict[str, Any]:
    """EXPLAIN (no ANALYZE) for a SELECT."""
    params = params or []
    guard = validate(sql)
    if not guard.ok:
        return {"error": guard.reason}

    explained = f"EXPLAIN (FORMAT JSON) {sql}"
    async with acquire() as conn:
        row = await conn.fetchrow(explained, *params)
    plan_raw = row[0] if row else None
    if isinstance(plan_raw, str):
        plan_raw = json.loads(plan_raw)
    return {"plan": plan_raw}


def _parse_qualified(name: str) -> tuple[str, str]:
    if "." in name:
        s, n = name.split(".", 1)
        return s.strip('"'), n.strip('"')
    return "public", name.strip('"')


def _apply_limit(sql: str, limit: int) -> str:
    stripped = sql.rstrip().rstrip(";").rstrip()
    lower = stripped.lower()
    if " limit " in lower:
        return stripped
    if lower.startswith("explain"):
        return stripped
    return f"{stripped} LIMIT {int(limit)}"
