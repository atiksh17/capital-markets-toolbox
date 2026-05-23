"""Schema introspection tools."""
from __future__ import annotations

from typing import Any

from ..config import settings
from ..db import acquire


async def list_tables(schema: str = "public") -> dict[str, Any]:
    if schema not in settings.schema_set:
        return {"error": f"Schema {schema!r} not allowed."}
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = $1 AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """
    async with acquire() as conn:
        rows = await conn.fetch(sql, schema)
    return {"schema": schema, "tables": [r["table_name"] for r in rows]}


async def describe_table(name: str, schema: str = "public") -> dict[str, Any]:
    if schema not in settings.schema_set:
        return {"error": f"Schema {schema!r} not allowed."}
    cols_sql = """
        SELECT column_name, data_type, is_nullable, column_default, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
    """
    pk_sql = """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = $1
          AND tc.table_name = $2
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
    """
    fk_sql = """
        SELECT a1.attname  AS from_col,
               n2.nspname  AS to_schema,
               c2.relname  AS to_table,
               a2.attname  AS to_col,
               con.conname AS constraint_name
        FROM pg_constraint con
        JOIN pg_class c1     ON c1.oid = con.conrelid
        JOIN pg_namespace n1 ON n1.oid = c1.relnamespace
        JOIN pg_class c2     ON c2.oid = con.confrelid
        JOIN pg_namespace n2 ON n2.oid = c2.relnamespace
        JOIN LATERAL unnest(con.conkey)  WITH ORDINALITY AS k(attnum, ord)  ON true
        JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS fk(attnum, ord) ON fk.ord = k.ord
        JOIN pg_attribute a1 ON a1.attrelid = c1.oid AND a1.attnum = k.attnum
        JOIN pg_attribute a2 ON a2.attrelid = c2.oid AND a2.attnum = fk.attnum
        WHERE con.contype = 'f'
          AND n1.nspname = $1
          AND c1.relname = $2
        ORDER BY from_col
    """
    async with acquire() as conn:
        cols = await conn.fetch(cols_sql, schema, name)
        pks = [r["column_name"] for r in await conn.fetch(pk_sql, schema, name)]
        fks = [dict(r) for r in await conn.fetch(fk_sql, schema, name)]

    if not cols:
        return {"error": f"Table {schema}.{name} not found."}

    return {
        "schema": schema,
        "name": name,
        "columns": [dict(c) for c in cols],
        "primary_key": pks,
        "foreign_keys": fks,
    }


async def list_foreign_keys() -> dict[str, Any]:
    sql = """
        SELECT n1.nspname  AS from_schema,
               c1.relname  AS from_table,
               a1.attname  AS from_col,
               n2.nspname  AS to_schema,
               c2.relname  AS to_table,
               a2.attname  AS to_col,
               con.conname AS constraint_name
        FROM pg_constraint con
        JOIN pg_class c1     ON c1.oid = con.conrelid
        JOIN pg_namespace n1 ON n1.oid = c1.relnamespace
        JOIN pg_class c2     ON c2.oid = con.confrelid
        JOIN pg_namespace n2 ON n2.oid = c2.relnamespace
        JOIN LATERAL unnest(con.conkey)  WITH ORDINALITY AS k(attnum, ord)  ON true
        JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS fk(attnum, ord) ON fk.ord = k.ord
        JOIN pg_attribute a1 ON a1.attrelid = c1.oid AND a1.attnum = k.attnum
        JOIN pg_attribute a2 ON a2.attrelid = c2.oid AND a2.attnum = fk.attnum
        WHERE con.contype = 'f'
          AND n1.nspname = ANY($1::text[])
        ORDER BY from_table, from_col
    """
    async with acquire() as conn:
        rows = await conn.fetch(sql, list(settings.schema_set))
    return {"edges": [dict(r) for r in rows]}


async def schema_summary() -> dict[str, Any]:
    tables_sql = """
        SELECT table_schema, table_name,
               (SELECT COUNT(*) FROM information_schema.columns c
                WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) AS column_count
        FROM information_schema.tables t
        WHERE table_schema = ANY($1::text[]) AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
    """
    fk_count_sql = """
        SELECT COUNT(*) FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE con.contype = 'f' AND n.nspname = ANY($1::text[])
    """
    async with acquire() as conn:
        tables = await conn.fetch(tables_sql, list(settings.schema_set))
        fk_count = await conn.fetchval(fk_count_sql, list(settings.schema_set))
    return {
        "schemas": sorted(settings.schema_set),
        "table_count": len(tables),
        "foreign_key_count": int(fk_count),
        "tables": [dict(t) for t in tables],
    }
