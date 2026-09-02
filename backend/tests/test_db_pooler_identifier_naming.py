"""Naming-contract regressions for the database pooler probe boundary."""

from __future__ import annotations

import ast
from pathlib import Path


_DB_SOURCE = Path(__file__).parents[1] / "app" / "db.py"


def _pooler_probe_function() -> ast.AsyncFunctionDef:
    """Return the pooler-probe AST from the repository-owned database module."""
    module_tree = ast.parse(_DB_SOURCE.read_text(encoding="utf-8"))
    for module_node in module_tree.body:
        if isinstance(module_node, ast.AsyncFunctionDef) and module_node.name == "_probe_pooler_admin_console":
            return module_node
    raise AssertionError("pooler probe function is missing")


def test_pooler_probe_uses_bounded_context_identifiers() -> None:
    """Require semantic names for the private pooler connection/query boundary."""
    probe_function = _pooler_probe_function()
    nested_functions = [
        function_node
        for function_node in probe_function.body
        if isinstance(function_node, ast.FunctionDef)
    ]
    assert [function_node.name for function_node in nested_functions] == ["_run_pooler_probe"]

    owned_names = {
        name_node.id
        for name_node in ast.walk(probe_function)
        if isinstance(name_node, ast.Name)
    }
    assert {"dsn", "password", "conn", "cur", "row"}.isdisjoint(owned_names)
    assert {
        "pooler_dsn",
        "pooler_password",
        "pooler_connection",
        "pooler_cursor",
        "version_row",
    }.issubset(owned_names)
