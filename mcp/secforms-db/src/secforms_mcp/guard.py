"""SQL guard: reject anything that isn't a pure read.

Belt + suspenders to the read-only Postgres role. Catches mistakes before
they hit the DB and returns a structured error so the LLM can fix the query.
"""
from __future__ import annotations

from dataclasses import dataclass

import pglast
from pglast import ast
from pglast.visitors import Visitor


WRITE_FUNCTIONS = {
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "pg_promote",
    "lo_create",
    "lo_unlink",
    "lo_import",
    "lo_export",
    "dblink_exec",
    "set_config",
}


FORBIDDEN_NODE_NAMES = {
    "InsertStmt", "UpdateStmt", "DeleteStmt", "MergeStmt",
    "CreateStmt", "DropStmt", "AlterTableStmt", "TruncateStmt",
    "GrantStmt", "GrantRoleStmt", "CopyStmt", "CreateRoleStmt",
    "AlterRoleStmt", "AlterRoleSetStmt", "DropRoleStmt",
    "VacuumStmt", "CreateFunctionStmt", "AlterFunctionStmt",
    "CreateSchemaStmt", "CreatedbStmt", "DropdbStmt",
    "AlterDatabaseStmt", "AlterDatabaseSetStmt",
    "IndexStmt", "CreateTrigStmt", "RenameStmt",
    "CreateSeqStmt", "AlterSeqStmt", "CommentStmt",
    "SecLabelStmt", "ClusterStmt", "ReindexStmt",
    "RefreshMatViewStmt", "CreateTableAsStmt", "ViewStmt",
    "RuleStmt", "CreatePolicyStmt", "AlterPolicyStmt",
    "CreatePublicationStmt", "AlterPublicationStmt",
    "CreateSubscriptionStmt", "AlterSubscriptionStmt", "DropSubscriptionStmt",
    "CreateExtensionStmt", "AlterExtensionStmt", "AlterExtensionContentsStmt",
    "AlterSystemStmt", "VariableSetStmt", "DoStmt", "CallStmt",
    "LockStmt", "DeallocateStmt", "PrepareStmt", "ExecuteStmt",
    "DeclareCursorStmt", "FetchStmt", "ClosePortalStmt",
    "NotifyStmt", "ListenStmt", "UnlistenStmt", "TransactionStmt",
    "DiscardStmt", "CheckPointStmt", "LoadStmt",
    "ImportForeignSchemaStmt", "ReassignOwnedStmt", "DropOwnedStmt",
}


@dataclass
class GuardResult:
    ok: bool
    reason: str | None = None
    statement_kind: str | None = None


def validate(sql: str) -> GuardResult:
    sql = (sql or "").strip()
    if not sql:
        return GuardResult(False, "Empty SQL.")

    try:
        statements = pglast.parse_sql(sql)
    except Exception as e:
        return GuardResult(False, f"SQL parse error: {e}")

    if len(statements) != 1:
        return GuardResult(False, "Multi-statement SQL is not allowed. Send one statement at a time.")

    stmt = statements[0].stmt
    kind = type(stmt).__name__

    if isinstance(stmt, ast.SelectStmt):
        err = _check_select(stmt)
        if err:
            return GuardResult(False, err, kind)
    elif isinstance(stmt, ast.ExplainStmt):
        inner = stmt.query
        if not isinstance(inner, ast.SelectStmt):
            return GuardResult(False, "EXPLAIN is only allowed for SELECT statements.", kind)
        err = _check_select(inner)
        if err:
            return GuardResult(False, err, kind)
        if _explain_has_analyze(stmt):
            return GuardResult(
                False,
                "EXPLAIN ANALYZE is not allowed (it executes the query).",
                kind,
            )
    else:
        return GuardResult(False, f"Statement type {kind!r} is not allowed. Only SELECT / WITH SELECT / EXPLAIN SELECT are permitted.", kind)

    err = _scan_for_writes(stmt)
    if err:
        return GuardResult(False, err, kind)

    return GuardResult(True, statement_kind=kind)


def _check_select(stmt: ast.SelectStmt) -> str | None:
    if stmt.intoClause is not None:
        return "SELECT INTO is not allowed (it creates a table)."
    if stmt.lockingClause:
        return "SELECT ... FOR UPDATE / FOR SHARE is not allowed."
    return None


def _explain_has_analyze(stmt: ast.ExplainStmt) -> bool:
    for opt in stmt.options or ():
        name = (getattr(opt, "defname", "") or "").lower()
        if name != "analyze":
            continue
        arg = getattr(opt, "arg", None)
        if arg is None:
            return True
        if isinstance(arg, ast.String):
            return (arg.sval or "").lower() in ("on", "true", "1", "t")
        if isinstance(arg, ast.Boolean):
            return bool(arg.boolval)
        if isinstance(arg, ast.Integer):
            return arg.ival != 0
        return True
    return False


class _WriteScanner(Visitor):
    def __init__(self) -> None:
        super().__init__()
        self.violation: str | None = None

    def visit(self, ancestors, node):
        name = type(node).__name__
        if name in FORBIDDEN_NODE_NAMES and self.violation is None:
            self.violation = f"Disallowed statement node {name} found in query tree."
        if isinstance(node, ast.FuncCall):
            parts = node.funcname or ()
            if parts and isinstance(parts[-1], ast.String):
                fname = (parts[-1].sval or "").lower()
                if fname in WRITE_FUNCTIONS and self.violation is None:
                    self.violation = f"Function {fname}() is not allowed."
        return None


def _scan_for_writes(node) -> str | None:
    scanner = _WriteScanner()
    scanner(node)
    return scanner.violation
