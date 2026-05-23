"""Async Postgres connection pool with read-only session defaults."""
from __future__ import annotations

from contextlib import asynccontextmanager

import asyncpg

from .config import settings


_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.pg_dsn,
            min_size=1,
            max_size=5,
            command_timeout=20.0,
            server_settings={
                "application_name": "secforms-mcp",
                "search_path": ",".join(settings.schema_set),
            },
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def acquire():
    pool = await init_pool()
    async with pool.acquire() as conn:
        yield conn


async def healthy() -> bool:
    try:
        async with acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False
