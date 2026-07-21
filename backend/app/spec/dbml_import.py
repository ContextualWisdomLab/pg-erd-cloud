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
blocks, ``indexes`` blocks, header colors. ponytail: line-oriented parser, not a
grammar — good for the 95% of DBML in the wild; a hostile file degrades to
skipped lines, never an exception.
"""

from __future__ import annotations

import re
import hashlib
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
    # Enforce aggregate input limit (e.g. 10 MiB) before processing to prevent CPU/memory exhaustion
    if len(text) > 10 * 1024 * 1024:
        raise ValueError("DBML input exceeds 10 MiB limit")
    """Parse DBML text into snapshot JSON (relations/columns/pk_columns/fk_edges)."""
    relations: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    pk_columns: list[dict[str, Any]] = []
    fk_specs: list[tuple[str, str, str, str, str, str]] = []  # child s/t/c, parent s/t/c

    oid_by_table: dict[tuple[str, str], int] = {}
    col_count_by_table: dict[int, int] = {}
    next_oid = 1
    current: tuple[str, str] | None = None
    in_ignored_block = 0
    in_indexes = False

    for raw_line in text.splitlines():
        # Limit overall memory usage: if DBML lines exceed 100000, stop parsing to prevent DoS attacks
        if len(columns) > 100000:
            break

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

        if line.startswith("}"):
            current = None
            in_indexes = False
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
        if re.match(r"^indexes\s*\{", line, re.IGNORECASE):
            in_indexes = True
            continue
        if in_indexes:
            if "}" in line:
                in_indexes = False
            continue

        cm = _COLUMN_RE.match(line)
        if not cm:
            continue
        col_name = (cm.group("qname") or cm.group("name")).strip('"')
        settings = (cm.group("settings") or "").lower()
        oid = oid_by_table[current]
        is_pk = bool(re.search(r"\bpk\b|primary\s+key", settings))
        col_position = col_count_by_table.setdefault(oid, 0) + 1
        col_count_by_table[oid] = col_position
        columns.append(
            {
                "relation_oid": oid,
                "column_name": col_name,
                # ⚡ Bolt: Use O(1) dictionary lookup instead of O(N) array scan for column positioning
                "column_position": col_count_by_table[oid],
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
        im = _INLINE_REF_RE.search(cm.group("settings") or "")
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
                "fk_constraint_name": _safe_constraint_name("fk", ct, cc),
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



def _safe_constraint_name(prefix: str, table: str, column: str = "") -> str:
    """Generate a deterministic, safe constraint name from attacker-controlled inputs.

    Replaces non-alphanumeric characters with underscores. If the result is longer
    than PostgreSQL's 63 byte limit, hashes the inputs for a unique, safe suffix.
    """
    raw = f"{prefix}_{table}"
    if column:
        raw += f"_{column}"

    # Allow only safe characters
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', raw)
    # Collapse multiple underscores
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')

    if len(safe_name) > 63:
        h = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:8]
        return f"{safe_name[:54]}_{h}"
    return safe_name

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
                "constraint_name": _safe_constraint_name("pk", rel["relation_name"]),
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
