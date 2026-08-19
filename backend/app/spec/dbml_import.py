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
blocks and header colors. Index blocks preserve simple identifier indexes and
skip expression indexes unless their identifiers are unambiguous. ponytail: line-oriented parser, not a
grammar — good for the 95% of DBML in the wild; a hostile file degrades to
skipped lines, never an exception.
"""

from __future__ import annotations

import re
from typing import Any

_COLUMN_RE = re.compile(
    r"^(?:\"(?P<qname>[^\"]+)\"|(?P<name>\w+))\s+"
    r"(?P<type>[\w]+(?:\([^)]*\))?(?:\[\])?)"
    r"(?:\s*\[(?P<settings>.*)\])?\s*$"
)
# a dotted path whose segments may be quoted (quotes can contain spaces)
_PATH = r'(?:"[^"]+"|\w+)(?:\.(?:"[^"]+"|\w+))*'
_REF_RE = re.compile(
    r"ref\s*(?:\w+\s*)?:?\s*"
    rf"(?P<from>{_PATH})\s*(?P<op>[<>-])\s*(?P<to>{_PATH})",
    re.IGNORECASE,
)
_INLINE_REF_RE = re.compile(rf"ref:\s*(?P<op>[<>-])\s*(?P<to>{_PATH})", re.IGNORECASE)
_PATH_SEGMENT_RE = re.compile(r'"[^"]+"|[^.]+')
_SAFE_INDEX_IDENTIFIER_RE = re.compile(r'^(?:"[^"]+"|[A-Za-z_]\w*)$')


def _split_top_level(value: str) -> list[str]:
    """Split comma-separated DBML values without splitting nested expressions."""
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    for index, character in enumerate(value):
        if quote:
            if character == quote and (index == 0 or value[index - 1] != "\\"):
                quote = None
            continue
        if character in "'\"":
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def _setting_value(settings: str, key: str) -> str | None:
    for part in _split_top_level(settings):
        name, separator, value = part.partition(":")
        if separator and name.strip().lower() == key:
            return value.strip() or None
    return None


def _has_setting(settings: str, key: str) -> bool:
    """Return whether a setting is present as a standalone DBML token."""
    return any(part.strip().lower() == key for part in _split_top_level(settings))


def _parenthesized_body(line: str) -> tuple[str, str] | None:
    if not line.startswith("("):
        return None
    depth = 0
    quote: str | None = None
    for index, character in enumerate(line):
        if quote:
            if character == quote and (index == 0 or line[index - 1] != "\\"):
                quote = None
            continue
        if character in "'\"":
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return line[1:index], line[index + 1 :].strip()
    return None


def _quote_index_identifier(value: str) -> str | None:
    value = value.strip()
    if not _SAFE_INDEX_IDENTIFIER_RE.fullmatch(value):
        return None
    return f'"{value.strip(chr(34))}"'


def _index_row(
    schema: str,
    table: str,
    relation_oid: int,
    index_columns: str,
    settings: str,
    ordinal: int,
) -> dict[str, Any] | None:
    columns = [_quote_index_identifier(value) for value in _split_top_level(index_columns)]
    if not columns or any(column is None for column in columns):
        return None
    safe_columns = [column for column in columns if column is not None]
    unique = _has_setting(settings, "unique")
    raw_name = _setting_value(settings, "name")
    index_name = (raw_name or f"idx_{table}_{ordinal}").strip("'\"")
    if not _SAFE_INDEX_IDENTIFIER_RE.fullmatch(index_name):
        index_name = f"idx_{table}_{ordinal}"
    quoted_table = f'"{schema}"."{table}"'
    quoted_name = f'"{index_name}"'
    index_def = (
        f'CREATE {"UNIQUE " if unique else ""}INDEX {quoted_name} '
        f"ON {quoted_table} ({', '.join(safe_columns)})"
    )
    return {
        "relation_oid": relation_oid,
        "index_name": index_name,
        "is_unique": unique,
        "is_primary": False,
        "is_valid": True,
        "predicate_expr": None,
        "index_def": index_def,
    }


def _consume_table_name(line: str, start: int) -> tuple[str, int] | None:
    """Return the table identifier and the offset after it, using only linear scans."""
    if start >= len(line):
        return None
    if line[start] == '"':
        end = line.find('"', start + 1)
        if end <= start + 1:
            return None
        return line[start + 1 : end], end + 1

    pos = start
    while pos < len(line) and (line[pos].isalnum() or line[pos] in "_."):
        pos += 1
    if pos == start:
        return None

    raw = line[start:pos]
    parts = raw.split(".")
    if any(part == "" for part in parts):
        return None
    return raw, pos


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
    consumed = _consume_table_name(line, pos)
    if consumed is None:
        return None
    raw_name, pos = consumed
    if not _table_header_tail_ok(line[pos:]):
        return None
    return _split_table_name(raw_name)


def _split_table_name(raw: str) -> tuple[str, str]:
    raw = raw.strip().strip('"')
    if "." in raw:
        schema, _, name = raw.partition(".")
        return schema.strip('"'), name.strip('"')
    return "public", raw


def _split_col_ref(raw: str) -> tuple[str, str, str]:
    """'schema.table.col' | 'table.col' -> (schema, table, col).

    Splits on dots *outside* quotes so '"Order Items".account_id' works.
    """
    parts = [p.strip('"') for p in _PATH_SEGMENT_RE.findall(raw.strip())]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return "public", parts[0], parts[1]
    return "public", "", parts[0]


def parse_dbml(text: str) -> dict[str, Any]:
    """Parse DBML text into snapshot JSON (relations/columns/pk_columns/fk_edges)."""
    relations: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    pk_columns: list[dict[str, Any]] = []
    indexes: list[dict[str, Any]] = []
    fk_specs: list[tuple[str, str, str, str, str, str]] = []  # child s/t/c, parent s/t/c

    oid_by_table: dict[tuple[str, str], int] = {}
    next_oid = 1
    current: tuple[str, str] | None = None
    in_ignored_block = 0
    in_indexes = False

    for raw_line in text.splitlines():
        # ReDoS guard: no legitimate DBML line approaches this length; capping
        # input size per regex call bounds worst-case backtracking to O(1).
        if len(raw_line) > 4096:
            continue
        line = raw_line.split("//", 1)[0].strip()
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

        # standalone Ref (works inside or outside a table body)
        if re.match(r"^ref\b", line, re.IGNORECASE):
            rm = _REF_RE.search(line)
            if rm:
                fs, ft, fc = _split_col_ref(rm.group("from"))
                ts, tt, tc = _split_col_ref(rm.group("to"))
                if rm.group("op") == "<":  # a < b means b references a
                    fs, ft, fc, ts, tt, tc = ts, tt, tc, fs, ft, fc
                if ft and tt:
                    fk_specs.append((fs, ft, fc, ts, tt, tc))
            continue

        if current is None:
            continue
        if in_indexes:
            if line.startswith("}"):
                in_indexes = False
                continue
            parsed_index = _parenthesized_body(line)
            if parsed_index is not None:
                index_columns, tail = parsed_index
                settings = tail[1:-1] if tail.startswith("[") and tail.endswith("]") else ""
                row = _index_row(
                    current[0],
                    current[1],
                    oid_by_table[current],
                    index_columns,
                    settings,
                    len(indexes) + 1,
                )
                if row is not None:
                    indexes.append(row)
            continue
        if line.startswith("}"):
            current = None
            continue
        if re.match(r"^indexes\s*\{", line, re.IGNORECASE):
            in_indexes = True
            continue

        cm = _COLUMN_RE.match(line)
        if not cm:
            continue
        col_name = (cm.group("qname") or cm.group("name")).strip('"')
        raw_settings = cm.group("settings") or ""
        settings = raw_settings.lower()
        oid = oid_by_table[current]
        default_expr = _setting_value(raw_settings, "default")
        is_pk = bool(re.search(r"\bpk\b|primary\s+key", settings))
        columns.append(
            {
                "relation_oid": oid,
                "column_name": col_name,
                "column_position": sum(1 for c in columns if c["relation_oid"] == oid) + 1,
                "data_type": cm.group("type"),
                "is_not_null": is_pk or "not null" in settings,
                "has_default": default_expr is not None,
                "default_expr": default_expr,
                "column_comment": None,
            }
        )
        if is_pk:
            pk_columns.append(
                {"relation_oid": oid, "column_name": col_name, "column_ordinal": len(pk_columns) + 1}
            )
        if _has_setting(raw_settings, "unique"):
            row = _index_row(
                current[0],
                current[1],
                oid,
                col_name,
                "unique",
                len(indexes) + 1,
            )
            if row is not None:
                indexes.append(row)
        im = _INLINE_REF_RE.search(raw_settings)
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
                "fk_constraint_name": f"fk_{ct}_{cc}",
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
        "indexes": indexes,
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
        quoted = ", ".join(f'"{c}"' for c in cols)
        constraints.append(
            {
                "constraint_oid": 200000 + oid,
                "constraint_name": f"pk_{rel['relation_name']}",
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
                    f'FOREIGN KEY ("{edge["child_column_name"]}") REFERENCES '
                    f'"{parent["schema_name"]}"."{parent["relation_name"]}" '
                    f'("{edge["parent_column_name"]}")'
                ),
            }
        )
    return constraints
