from __future__ import annotations

import argparse
import ast
from pathlib import Path

_SKIP_DIR_NAMES = {
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


def _iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _has_sys_path_mutation(src: str) -> bool:
    # A simple, conservative heuristic.
    needles = (
        "sys.path.append",
        "sys.path.insert",
        "sys.path +=",
        "sys.path =",
    )
    return any(n in src for n in needles)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check import safety (relative/wildcard/sys.path mutations)."
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Repository root (absolute path recommended).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.root).resolve()
    targets: list[Path] = []

    for rel in ("backend", "scripts"):
        p = repo_root / rel
        if p.is_dir():
            targets.append(p)

    if not targets:
        print("No targets found; skipping.")
        return 0

    errors: list[str] = []
    warnings: list[str] = []

    self_path = Path(__file__).resolve()

    for target in targets:
        for file_path in _iter_python_files(target):
            if file_path.resolve() == self_path:
                # Avoid false-positives from the checker searching for its own
                # detection strings.
                continue
            src = file_path.read_text(encoding="utf-8")
            if _has_sys_path_mutation(src):
                errors.append(f"{file_path}: sys.path mutation detected")

            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        errors.append(
                            f"{file_path}:{node.lineno} relative import detected"
                        )
                    for alias in node.names:
                        if alias.name == "*":
                            errors.append(
                                f"{file_path}:{node.lineno} wildcard import detected"
                            )

                # Warn for imports nested in functions/classes (can be valid, but
                # often indicates implicit dependency ordering).
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    for child in node.body:
                        if isinstance(child, (ast.Import, ast.ImportFrom)):
                            warnings.append(
                                f"{file_path}:{child.lineno} import not at top-level"
                            )

    for w in sorted(set(warnings)):
        print(f"WARN: {w}")

    if errors:
        for e in sorted(set(errors)):
            print(f"ERROR: {e}")
        return 1

    print("OK: import safety checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
