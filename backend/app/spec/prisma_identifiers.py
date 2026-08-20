"""Collision-free Prisma identifier allocation for snapshot ORM export.

The grammar and reserved-name tables are pinned to the Prisma Schema API and
the prisma-engines reserved-model-name list. Canvas export uses the same
contract in ``frontend/src/erd/prismaIdentifierContract.ts``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Literal

PRISMA_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
PRISMA_IDENTIFIER_CONTRACT_VERSION = "2026-08-16.prisma-6-reserved"
PRISMA_IDENTIFIER_MAX_ATTEMPTS = 10_000
PRISMA_EXPORT_FAILURE_SCHEMA = (
    "// Prisma export failed.\n"
    "// A unique identifier could not be allocated within the configured bound.\n"
    "// Download the diagnostic manifest, rename colliding tables or columns, then export again.\n"
)

PRISMA_SCHEMA_KEYWORDS = frozenset(
    {"datasource", "enum", "generator", "model", "type", "view"}
)
PRISMA_SCALAR_TYPE_NAMES = frozenset(
    {
        "BigInt",
        "Boolean",
        "Bytes",
        "DateTime",
        "Decimal",
        "Float",
        "Int",
        "Json",
        "String",
        "Unsupported",
    }
)
PRISMA_CLIENT_RESERVED_NAMES = frozenset(
    {
        "PrismaClient",
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "implements",
        "import",
        "in",
        "instanceof",
        "interface",
        "let",
        "new",
        "null",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "using",
        "var",
        "void",
        "while",
        "with",
        "yield",
    }
)

PrismaIdentifierKind = Literal["model", "field", "relation"]


def is_prisma_identifier(name: str) -> bool:
    """Return whether ``name`` matches the Prisma identifier grammar."""
    return bool(PRISMA_IDENTIFIER_PATTERN.fullmatch(name))


def is_reserved_prisma_name(name: str) -> bool:
    """Return whether ``name`` is reserved for a Prisma model, enum, or type."""
    return (
        name.lower() in PRISMA_SCHEMA_KEYWORDS
        or name in PRISMA_SCALAR_TYPE_NAMES
        or name in PRISMA_CLIENT_RESERVED_NAMES
    )


def preferred_prisma_name(source: str) -> str:
    """Collapse a database name to a Prisma grammar candidate.

    Non-ASCII, punctuation, and whitespace become ``_``. Leading digits use
    the ``M_`` prefix. Reserved names take a trailing ``_`` so they do not
    collide with a source already named ``M_model``.
    """
    normalized = unicodedata.normalize("NFC", source)
    candidate = re.sub(r"[^A-Za-z0-9_]+", "_", normalized)
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    if not candidate:
        candidate = "unnamed"
    if not candidate[0].isalpha():
        candidate = f"M_{candidate}"
    if is_reserved_prisma_name(candidate) or not is_prisma_identifier(candidate):
        candidate = f"{candidate}_"
    return candidate


def allocate_prisma_identifiers(
    requests: list[dict[str, str]],
    max_attempts: int = PRISMA_IDENTIFIER_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Allocate deterministic, collision-free Prisma identifiers.

    ``requests`` items use keys ``key``, ``kind``, ``namespace``, ``source``,
    and optional ``preferred``. Allocation order is source text, then
    namespace, then key, so input order cannot change the mapping.
    """
    names: dict[str, str] = {}
    mappings: list[dict[str, str]] = []
    used_by_namespace: dict[str, set[str]] = {}
    ordered = sorted(
        requests,
        key=lambda item: (item["source"], item["namespace"], item["key"]),
    )
    for request in ordered:
        used = used_by_namespace.setdefault(request["namespace"], set())
        base = request.get("preferred") or preferred_prisma_name(request["source"])
        candidate = base
        suffix = 2
        attempts = 0
        while (
            candidate in used
            or not is_prisma_identifier(candidate)
            or is_reserved_prisma_name(candidate)
        ):
            attempts += 1
            if attempts > max_attempts:
                return {
                    "ok": False,
                    "names": names,
                    "mappings": mappings,
                    "failure": {
                        "key": request["key"],
                        "kind": request["kind"],
                        "namespace": request["namespace"],
                        "source": request["source"],
                        "preferred": base,
                        "lastCandidate": candidate,
                        "attempts": attempts,
                        "maxAttempts": max_attempts,
                    },
                }
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        names[request["key"]] = candidate
        mappings.append(
            {
                "kind": request["kind"],
                "namespace": request["namespace"],
                "source": request["source"],
                "generated": candidate,
            }
        )
    return {"ok": True, "names": names, "mappings": mappings}


def build_prisma_manifest(
    mappings: list[dict[str, str]], failure: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the export manifest recorded beside a generated schema."""
    manifest: dict[str, Any] = {
        "contractVersion": PRISMA_IDENTIFIER_CONTRACT_VERSION,
        "mappings": mappings,
    }
    if failure is not None:
        manifest["failure"] = failure
    return manifest


def quote_prisma_string(value: str) -> str:
    """Quote a source identifier for ``@map`` / ``@@map``."""
    return json.dumps(value)
