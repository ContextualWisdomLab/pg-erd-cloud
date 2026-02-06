from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "site-packages",
    "build",
    "dist",
}


def iter_python_files(root: Path) -> Iterable[Path]:
    """Yield Python files under root, skipping common build/cache dirs."""
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path
