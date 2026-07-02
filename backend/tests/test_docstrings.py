"""Docstring coverage checks for backend public APIs touched by this PR."""

from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
CHECKED_MODULES = (
    BACKEND_ROOT / "app" / "snowflake_introspect" / "introspect.py",
)


def _public_defs(tree: ast.AST) -> list[ast.AsyncFunctionDef | ast.ClassDef | ast.FunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef))
        and not node.name.startswith("_")
    ]


def test_changed_public_backend_apis_have_docstrings() -> None:
    missing: list[str] = []
    for module_path in CHECKED_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in _public_defs(tree):
            if ast.get_docstring(node):
                continue
            rel_path = module_path.relative_to(BACKEND_ROOT).as_posix()
            missing.append(f"{rel_path}:{node.lineno} {node.name}")

    assert missing == []
