from __future__ import annotations

import argparse
import ast
from pathlib import Path

from scripts.python_checks.file_utils import iter_python_files


def _is_sys_path(expr: ast.AST) -> bool:
    return (
        isinstance(expr, ast.Attribute)
        and expr.attr == "path"
        and isinstance(expr.value, ast.Name)
        and expr.value.id == "sys"
    )


def _has_sys_path_mutation(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        # sys.path.append(...) / sys.path.insert(...) / sys.path.extend(...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in (
                "append",
                "insert",
                "extend",
            ) and _is_sys_path(node.func.value):
                return True

        # sys.path += ...
        if isinstance(node, ast.AugAssign) and _is_sys_path(node.target):
            return True

        # sys.path = ...
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _is_sys_path(target):
                    return True
    return False


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
        for file_path in iter_python_files(target):
            if file_path.resolve() == self_path:
                # Avoid false-positives from the checker searching for its own
                # detection strings.
                continue
            try:
                src = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                warnings.append(f"{file_path}: read failed ({exc})")
                continue

            try:
                tree = ast.parse(src)
            except SyntaxError as exc:
                warnings.append(
                    f"{file_path}: SyntaxError ({exc.msg}) at line {exc.lineno}"
                )
                continue

            if _has_sys_path_mutation(tree):
                errors.append(f"{file_path}: sys.path mutation detected")

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
                    for child in ast.walk(node):
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
