"""Parse DBML (database markup language) into the common snapshot JSON.

Design-first workflow: write DBML (the dbdiagram.io/dbdocs dialect), convert it
to the same snapshot shape introspection produces, and every downstream feature
works on it unchanged — DDL export, migration generation, analyzers, the ERD.

Supported subset (the parts real DBML files actually use):

* ``Table [schema.]name { ... }`` with columns ``name type [settings]``
* column settings: ``pk``/``primary key``, ``not null``, ``unique``, ``default:``,
  ``note:``, inline ``ref: > other.col`` (also ``<`` and ``-``)
* standalone ``Ref: a.col > b.col`` / ``Ref name { a.col > b.col }``
* quoted identifiers ``"My Table"``; comments ``//``; multi-word types

Ignored (parsed over, not errors): ``Project``/``Enum``/``TableGroup``/``Note``
blocks, ``indexes`` blocks, header colors. This is a bounded line-oriented
parser, not a complete grammar. Unsupported ordinary lines are skipped, while
ambiguous identifiers and resource-limit violations fail closed.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.ddl.export import quote_identifier


class DbmlIdentifierError(ValueError):
    """Raised when DBML identifier text cannot be represented safely."""


_POSTGRES_IDENTIFIER_MAX_BYTES = 63
_DBML_MAX_CHARACTERS = 524_288
_DBML_MAX_LINES = 10_000
_COLUMN_TAIL_RE = re.compile(
    r"^(?P<type>[\w]+(?:\([^)]*\))?(?:\[\])?)"
    r"(?:\s*\[(?P<settings>.*)\])?\s*$"
)
# a dotted path whose segments may be quoted (quotes can contain spaces)
_PATH = r'(?:"(?:""|[^"])+"|\w+)(?:\.(?:"(?:""|[^"])+"|\w+))*'
_REF_RE = re.compile(
    r"ref\s*(?:\w+\s*)?:?\s*"
    rf"(?P<from>{_PATH})\s*(?P<op>[<>-])\s*(?P<to>{_PATH})",
    re.IGNORECASE,
)
_INLINE_REF_RE = re.compile(rf"ref:\s*(?P<op>[<>-])\s*(?P<to>{_PATH})", re.IGNORECASE)
_PATH_SEGMENT_RE = re.compile(r'"(?:""|[^"])+"|[^.]+')


def _validate_identifier(identifier: str) -> str:
    """Validate one decoded identifier against PostgreSQL's lossless boundary."""
    if not identifier:
        raise DbmlIdentifierError("DBML identifiers must not be empty")
    if "\x00" in identifier:
        raise DbmlIdentifierError("DBML identifiers must not contain NUL")
    if len(identifier.encode("utf-8")) > _POSTGRES_IDENTIFIER_MAX_BYTES:
        raise DbmlIdentifierError("DBML identifier exceeds 63 UTF-8 bytes")
    return identifier


def _consume_identifier(line: str, start: int) -> tuple[str, int] | None:
    """Decode one quoted or unquoted DBML identifier from ``line``."""
    if start >= len(line):
        return None
    if line[start] == '"':
        pos = start + 1
        decoded: list[str] = []
        while pos < len(line):
            if line[pos] != '"':
                decoded.append(line[pos])
                pos += 1
                continue
            if pos + 1 < len(line) and line[pos + 1] == '"':
                decoded.append('"')
                pos += 2
                continue
            return _validate_identifier("".join(decoded)), pos + 1
        raise DbmlIdentifierError("unterminated quoted DBML identifier")

    pos = start
    while pos < len(line) and (line[pos].isalnum() or line[pos] == "_"):
        pos += 1
    if pos == start:
        return None
    return _validate_identifier(line[start:pos]), pos


def _consume_identifier_path(
    line: str, start: int, *, maximum_segments: int
) -> tuple[list[str], int] | None:
    """Decode a bounded dotted identifier path without ambiguous segmentation."""
    first = _consume_identifier(line, start)
    if first is None:
        return None
    identifier, pos = first
    segments = [identifier]
    while pos < len(line) and line[pos] == ".":
        if len(segments) >= maximum_segments:
            raise DbmlIdentifierError("DBML identifier path has too many segments")
        following = _consume_identifier(line, pos + 1)
        if following is None:
            raise DbmlIdentifierError("DBML identifier path contains an empty segment")
        identifier, pos = following
        segments.append(identifier)
    return segments, pos


def _strip_dbml_comment(line: str) -> str:
    """Remove ``//`` comments only when the marker is outside quoted names."""
    pos = 0
    in_quote = False
    while pos < len(line):
        if line[pos] == '"':
            if in_quote and pos + 1 < len(line) and line[pos + 1] == '"':
                pos += 2
                continue
            in_quote = not in_quote
            pos += 1
            continue
        if not in_quote and line.startswith("//", pos):
            return line[:pos]
        pos += 1
    return line


def _bounded_derived_identifier(candidate: str) -> str:
    """Keep a generated identifier stable without PostgreSQL truncation."""
    encoded = candidate.encode("utf-8")
    if len(encoded) <= _POSTGRES_IDENTIFIER_MAX_BYTES:
        return candidate
    digest = hashlib.sha256(encoded).hexdigest()[:8]
    byte_budget = _POSTGRES_IDENTIFIER_MAX_BYTES - len(digest) - 1
    prefix: list[str] = []
    used = 0
    for character in candidate:
        width = len(character.encode("utf-8"))
        if used + width > byte_budget:
            break
        prefix.append(character)
        used += width
    return f"{''.join(prefix)}_{digest}"


def _table_header_tail_ok(tail: str) -> bool:
    """Validate what may follow a ``Table <name>`` header on the same line.

    Grammar (whitespace-insensitive): an optional ``as <alias>`` rename followed
    by an optional opening ``{`` (dbdiagram also allows the brace on the next
    line). Implemented with plain string scanning rather than a regex so there
    is no backtracking.
    """
    rest = tail.strip()
    if not rest:
        return True
    if rest[:2].lower() == "as" and (len(rest) == 2 or rest[2].isspace()):
        rest = rest[2:].lstrip()
        alias_len = 0
        while alias_len < len(rest) and (
            rest[alias_len].isalnum() or rest[alias_len] == "_"
        ):
            alias_len += 1
        if alias_len == 0:
            return False
        rest = rest[alias_len:].lstrip()
    return rest in ("", "{")


def _parse_table_header(line: str) -> tuple[str, str] | None:
    """Parse ``Table [schema.]name`` headers without regex backtracking."""
    if len(line) < 6 or line[:5].lower() != "table" or not line[5].isspace():
        return None
    pos = 5
    while pos < len(line) and line[pos].isspace():
        pos += 1
    consumed = _consume_identifier_path(line, pos, maximum_segments=2)
    if consumed is None:
        return None
    segments, pos = consumed
    if not _table_header_tail_ok(line[pos:]):
        return None
    if len(segments) == 2:
        return segments[0], segments[1]
    return "public", segments[0]


def _split_col_ref(raw: str) -> tuple[str, str, str]:
    """'schema.table.col' | 'table.col' -> (schema, table, col).

    Splits on dots *outside* quotes so '"Order Items".account_id' works.
    """
    parts = [
        p[1:-1].replace('""', '"') if p.startswith('"') else p
        for p in _PATH_SEGMENT_RE.findall(raw.strip())
    ]
    for part in parts:
        _validate_identifier(part)
    if len(parts) > 3:
        raise DbmlIdentifierError("DBML reference path has too many segments")
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return "public", parts[0], parts[1]
    return "public", "", parts[0]


def _parse_column(line: str) -> tuple[str, re.Match[str]] | None:
    """Parse a column line after decoding its identifier exactly once."""
    consumed = _consume_identifier(line, 0)
    if consumed is None:
        return None
    column_name, pos = consumed
    if pos >= len(line) or not line[pos].isspace():
        return None
    tail = line[pos:].lstrip()
    match = _COLUMN_TAIL_RE.match(tail)
    if match is None:
        return None
    return column_name, match


def parse_dbml(text: str) -> dict[str, Any]:
    """Parse DBML text into snapshot JSON (relations/columns/pk_columns/fk_edges)."""
    if len(text) > _DBML_MAX_CHARACTERS:
        raise DbmlIdentifierError("DBML text exceeds 524288 characters")

    relations: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    pk_columns: list[dict[str, Any]] = []
    fk_specs: list[tuple[str, str, str, str, str, str]] = []  # child s/t/c, parent s/t/c

    oid_by_table: dict[tuple[str, str], int] = {}
    next_oid = 1
    current: tuple[str, str] | None = None
    in_ignored_block = 0
    in_indexes = False
    col_counts_by_oid: dict[int, int] = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if line_number > _DBML_MAX_LINES:
            raise DbmlIdentifierError("DBML text exceeds 10000 lines")
        # ReDoS guard: no legitimate DBML line approaches this length; capping
        # input size per regex call bounds worst-case backtracking to O(1).
        if len(raw_line) > 4096:
            raise DbmlIdentifierError("DBML line exceeds 4096 characters")
        if "\x00" in raw_line:
            raise DbmlIdentifierError("DBML text must not contain NUL")
        line = _strip_dbml_comment(raw_line).strip()
        if not line:
            continue

        # ignored blocks (Project / Enum / TableGroup / Note) — track braces
        if in_ignored_block:
            in_ignored_block += line.count("{") - line.count("}")
            continue
        if re.match(r"^(project|enum|tablegroup|note)\b", line, re.IGNORECASE):
            in_ignored_block = line.count("{") - line.count("}")
            if in_ignored_block <= 0 and "{" not in line:
                in_ignored_block = 1  # block opens on a following line
            continue

        table_name = _parse_table_header(line)
        if table_name is not None:
            schema, name = table_name
            current = (schema, name)
            if current not in oid_by_table:
                oid_by_table[current] = next_oid
                relations.append(
                    {
                        "relation_oid": next_oid,
                        "relation_kind": "r",
                        "schema_name": schema,
                        "relation_name": name,
                        "relation_comment": None,
                    }
                )
                next_oid += 1
            continue

        if line.startswith("}"):
            current = None
            in_indexes = False
            continue

        # standalone Ref (works inside or outside a table body)
        if re.match(r"^ref\b", line, re.IGNORECASE):
            rm = _REF_RE.search(line)
            if rm is None:
                if '"' in line:
                    raise DbmlIdentifierError("invalid DBML reference expression")
                continue
            fs, ft, fc = _split_col_ref(rm.group("from"))
            ts, tt, tc = _split_col_ref(rm.group("to"))
            if rm.group("op") == "<":  # a < b means b references a
                fs, ft, fc, ts, tt, tc = ts, tt, tc, fs, ft, fc
            if ft and tt:
                fk_specs.append((fs, ft, fc, ts, tt, tc))
            continue

        if current is None:
            continue
        if re.match(r"^indexes\s*\{", line, re.IGNORECASE):
            in_indexes = True
            continue
        if in_indexes:
            if "}" in line:
                in_indexes = False
            continue

        parsed_column = _parse_column(line)
        if parsed_column is None:
            continue
        col_name, cm = parsed_column
        settings = (cm.group("settings") or "").lower()
        oid = oid_by_table[current]
        is_pk = bool(re.search(r"\bpk\b|primary\s+key", settings))
        column_position = col_counts_by_oid.get(oid, 0) + 1
        col_counts_by_oid[oid] = column_position
        columns.append(
            {
                "relation_oid": oid,
                "column_name": col_name,
                "column_position": column_position,
                "data_type": cm.group("type"),
                "is_not_null": is_pk or "not null" in settings,
                "has_default": "default:" in settings,
                "default_expr": None,
                "column_comment": None,
            }
        )
        if is_pk:
            pk_columns.append(
                {"relation_oid": oid, "column_name": col_name, "column_ordinal": len(pk_columns) + 1}
            )
        raw_settings = cm.group("settings") or ""
        im = _INLINE_REF_RE.search(raw_settings)
        if re.search(r"\bref\s*:", raw_settings, re.IGNORECASE) and im is None:
            raise DbmlIdentifierError("invalid inline DBML reference expression")
        if im:
            ts, tt, tc = _split_col_ref(im.group("to"))
            if im.group("op") == "<":
                # inverse inline ref: the other table references this column
                fk_specs.append((ts, tt, tc, current[0], current[1], col_name))
            else:
                fk_specs.append((current[0], current[1], col_name, ts, tt, tc))

    fk_edges: list[dict[str, Any]] = []
    for i, (cs, ct, cc, ps, pt, pc) in enumerate(fk_specs, start=1):
        child = oid_by_table.get((cs, ct))
        parent = oid_by_table.get((ps, pt))
        if child is None or parent is None:
            continue  # ref to a table not defined in this document
        fk_edges.append(
            {
                "fk_constraint_oid": 100000 + i,
                "fk_constraint_name": _bounded_derived_identifier(f"fk_{ct}_{cc}"),
                "child_relation_oid": child,
                "parent_relation_oid": parent,
                "child_column_name": cc,
                "parent_column_name": pc,
                "column_ordinal": 1,
            }
        )

    constraints = _build_constraints(relations, columns, pk_columns, fk_edges)

    return {
        "source": "dbml",
        "schemas": sorted({r["schema_name"] for r in relations}),
        "relations": relations,
        "columns": columns,
        "constraints": constraints,
        "indexes": [],
        "pk_columns": pk_columns,
        "fk_edges": fk_edges,
        "citus_distributed_tables": [],
    }


def _build_constraints(
    relations: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    pk_columns: list[dict[str, Any]],
    fk_edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive the ``constraints`` array (what DDL export renders) from parsed parts."""
    rel_by_oid = {r["relation_oid"]: r for r in relations}
    pos_by_oid_col: dict[tuple[int, str], int] = {
        (c["relation_oid"], c["column_name"]): c["column_position"] for c in columns
    }
    constraints: list[dict[str, Any]] = []

    pk_cols_by_oid: dict[int, list[str]] = {}
    for pk in pk_columns:
        pk_cols_by_oid.setdefault(pk["relation_oid"], []).append(pk["column_name"])
    for oid, cols in pk_cols_by_oid.items():
        rel = rel_by_oid[oid]
        quoted = ", ".join(quote_identifier(c) for c in cols)
        constraints.append(
            {
                "constraint_oid": 200000 + oid,
                "constraint_name": _bounded_derived_identifier(
                    f"pk_{rel['relation_name']}"
                ),
                "constraint_type": "p",
                "schema_name": rel["schema_name"],
                "relation_oid": oid,
                "relation_name": rel["relation_name"],
                "constrained_attnums": [pos_by_oid_col[(oid, c)] for c in cols],
                "constraint_def": f"PRIMARY KEY ({quoted})",
            }
        )

    for edge in fk_edges:
        child = rel_by_oid[edge["child_relation_oid"]]
        parent = rel_by_oid[edge["parent_relation_oid"]]
        constraints.append(
            {
                "constraint_oid": 300000 + edge["fk_constraint_oid"],
                "constraint_name": edge["fk_constraint_name"],
                "constraint_type": "f",
                "schema_name": child["schema_name"],
                "relation_oid": edge["child_relation_oid"],
                "relation_name": child["relation_name"],
                "constrained_attnums": [
                    pos_by_oid_col.get(
                        (edge["child_relation_oid"], edge["child_column_name"]), 1
                    )
                ],
                "constraint_def": (
                    f"FOREIGN KEY ({quote_identifier(edge['child_column_name'])}) "
                    f"REFERENCES {quote_identifier(parent['schema_name'])}."
                    f"{quote_identifier(parent['relation_name'])} "
                    f"({quote_identifier(edge['parent_column_name'])})"
                ),
            }
        )
    return constraints
