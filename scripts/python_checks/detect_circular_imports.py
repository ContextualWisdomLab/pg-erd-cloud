from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path

from scripts.python_checks.check_import_safety import iter_python_files


def _module_name(package_name: str, package_dir: Path, file_path: Path) -> str:
    rel = file_path.relative_to(package_dir).with_suffix("")
    parts = [package_name, *rel.parts]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_to_known(import_name: str, known_modules: set[str]) -> str | None:
    parts = import_name.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in known_modules:
            return candidate
    return None


def _collect_internal_imports(
    src: str, *, module_prefix: str, known_modules: set[str]
) -> set[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # Keep this checker non-blocking on syntax errors; those should be
        # caught by linters/typecheckers.
        return set()

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == module_prefix or name.startswith(
                    f"{module_prefix}."
                ):
                    resolved = _resolve_to_known(name, known_modules)
                    if resolved:
                        imported.add(resolved)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative imports are handled by check_import_safety.
                continue
            if not node.module:
                continue
            base = node.module
            if base == module_prefix or base.startswith(f"{module_prefix}."):
                # Handle cases like:
                #   from app import models
                # where `node.module` is "app" but the imported module is
                # "app.models".
                for alias in node.names:
                    candidates: list[str]
                    if alias.name == "*":
                        candidates = [base]
                    else:
                        candidates = [f"{base}.{alias.name}", base]

                    for candidate in candidates:
                        resolved = _resolve_to_known(candidate, known_modules)
                        if resolved:
                            imported.add(resolved)
                            break
    return imported


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    visited: set[str] = set()
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)
        on_stack.add(node)

        for nxt in graph.get(node, set()):
            if nxt not in visited:
                dfs(nxt)
            elif nxt in on_stack:
                # Extract cycle path.
                idx = stack.index(nxt)
                cycle = [*stack[idx:], nxt]
                # Deduplicate: store normalized string form.
                cycles.append(cycle)

        stack.pop()
        on_stack.remove(node)

    for start in sorted(graph.keys()):
        if start not in visited:
            dfs(start)

    # Deduplicate cycles by canonical rotation.
    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for cycle in cycles:
        if len(cycle) < 3:
            continue
        core = cycle[:-1]
        rotations = [tuple(core[i:] + core[:i]) for i in range(len(core))]
        key = min(rotations)
        if key in seen:
            continue
        seen.add(key)
        unique.append([*key, key[0]])
    return unique


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect circular imports in internal packages."
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Repository root (absolute path recommended).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.root).resolve()

    # Project convention: backend/app is importable as top-level package 'app'.
    packages: list[tuple[str, Path]] = []
    backend_app = repo_root / "backend" / "app"
    if backend_app.is_dir():
        packages.append(("app", backend_app))

    if not packages:
        print("No known package directories found; skipping.")
        return 0

    known_modules: set[str] = set()
    file_to_module: dict[Path, str] = {}
    for package_name, package_dir in packages:
        for file_path in iter_python_files(package_dir):
            mod = _module_name(package_name, package_dir, file_path)
            known_modules.add(mod)
            file_to_module[file_path] = mod

    graph: dict[str, set[str]] = defaultdict(set)
    for file_path, mod in file_to_module.items():
        try:
            src = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            print(f"WARN: failed to read {file_path}: {exc}")
            continue
        internal_imports = _collect_internal_imports(
            src, module_prefix=mod.split(".")[0], known_modules=known_modules
        )
        for imported in internal_imports:
            if imported != mod:
                graph[mod].add(imported)

    cycles = _find_cycles(graph)
    if not cycles:
        print("OK: no circular imports detected")
        return 0

    print("ERROR: circular imports detected")
    for cycle in cycles:
        print("  - " + " -> ".join(cycle))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
