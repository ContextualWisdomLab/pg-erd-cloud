"""Parse DBML (database markup language) into the common snapshot JSON.

Design-first workflow: write DBML (the dbdiagram.io/dbdocs dialect), convert it
to the same snapshot shape introspection produces, and every downstream feature
works on it unchanged — DDL export, migration generation, analyzers, the ERD.

Supported subset (the parts real DBML files actually use):

* ``Table [schema.]name { ... }`` with columns ``name type [settings]``
* column settings: ``pk``/``primary key``, ``not null``, ``unique``, ``default:``,
  ``note:``, inline ``ref: > other.col`` (also ``<`` and ``-``)
* standalone ``Ref: a.col > b.col`` / ``Ref name { a.col > b.col }``
* simple ``indexes { (column_a, column_b) [unique] }`` blocks
* quoted identifiers ``"My Table"``; comments ``//``; multi-word types

Ignored (parsed over, not errors): ``Project``/``Enum``/``TableGroup``/``Note``
blocks and header colors. Index expressions/settings that are outside the
bounded simple-column subset are skipped. ponytail: line-oriented parser, not
a grammar — good for the 95% of DBML in the wild; a hostile file degrades to
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


def _split_csv(value: str) -> list[str] | None:
    """Split a bounded comma list while allowing quoted identifiers/settings."""
    parts: list[str] = []
    start = 0
    quote = False
    for position, char in enumerate(value):
        if char == '"':
            quote = not quote
        elif char == "," and not quote:
            part = value[start:position].strip()
            if not part:
                return None
            parts.append(part)
            start = position + 1
    if quote:
        return None
    part = value[start:].strip()
    if not part:
        return None
    parts.append(part)
    return parts


def _parse_index_line(
    line: str,
) -> tuple[list[str], bool, bool, str, str | None] | None:
    """Parse only simple DBML index tuples; hostile/expressive lines are skipped."""
    if not line.startswith("("):
        return None
    quoted = False
    closing = -1
    for position, char in enumerate(line[1:], start=1):
        if char == '"':
            quoted = not quoted
        elif char == ")" and not quoted:
            closing = position
            break
    if closing <= 1:
        return None
    columns = _split_csv(line[1:closing])
    if columns is None:
        return None
    parsed_columns: list[str] = []
    for column in columns:
        match = re.fullmatch(r'"([^"]+)"|([A-Za-z_]\w*)', column)
        if match is None:
            return None
        parsed_columns.append(match.group(1) or match.group(2))

    tail = line[closing + 1 :].strip().rstrip(";").strip()
    if not tail:
        settings: list[str] = []
    elif tail.startswith("[") and tail.endswith("]"):
        settings = _split_csv(tail[1:-1]) or []
    else:
        return None

    unique = False
    primary = False
    access_method = "btree"
    explicit_name: str | None = None
    for setting in settings:
        key, separator, raw_value = setting.partition(":")
        key = key.strip().lower()
        value = raw_value.strip().strip("'\"") if separator else ""
        if key in {"unique"} or (not separator and key == "unique"):
            unique = True
        elif key in {"pk", "primary", "primary key"} or (
            not separator and key in {"pk", "primary", "primary key"}
        ):
            primary = True
            unique = True
        elif key in {"type", "method"} and re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]{0,62}", value
        ):
            access_method = value
        elif key == "name" and value and len(value) <= 128:
            explicit_name = value
    return parsed_columns, unique, primary, access_method, explicit_name


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _index_name(base: str, ordinal: int, preserve: bool = False) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", base).strip("_") or "index"
    if safe[0].isdigit():
        safe = f"ix_{safe}"
    if preserve:
        return safe[:63]
    suffix = f"_{ordinal}"
    return f"{safe[: 63 - len(suffix)]}{suffix}"


def parse_dbml(text: str) -> dict[str, Any]:
    """Parse DBML text into the common snapshot JSON shape."""
    relations: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    pk_columns: list[dict[str, Any]] = []
    fk_specs: list[
        tuple[str, str, str, str, str, str]
    ] = []  # child s/t/c, parent s/t/c
    index_specs: list[
        tuple[tuple[str, str], list[str], bool, bool, str, str | None, int]
    ] = []
    index_ordinals: dict[tuple[str, str], int] = {}

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

        if current is not None and in_indexes:
            if line.startswith("}"):
                in_indexes = False
                continue
            parsed_index = _parse_index_line(line)
            if parsed_index is not None:
                ordinal = index_ordinals.get(current, 0) + 1
                index_ordinals[current] = ordinal
                index_specs.append((current, *parsed_index, ordinal))
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

        cm = _COLUMN_RE.match(line)
        if not cm:
            continue
        col_name = (cm.group("qname") or cm.group("name")).strip('"')
        settings = (cm.group("settings") or "").lower()
        oid = oid_by_table[current]
        is_pk = bool(re.search(r"\bpk\b|primary\s+key", settings))
        columns.append(
            {
                "relation_oid": oid,
                "column_name": col_name,
                "column_position": sum(1 for c in columns if c["relation_oid"] == oid)
                + 1,
                "data_type": cm.group("type"),
                "is_not_null": is_pk or "not null" in settings,
                "has_default": "default:" in settings,
                "default_expr": None,
                "column_comment": None,
            }
        )
        if is_pk:
            pk_columns.append(
                {
                    "relation_oid": oid,
                    "column_name": col_name,
                    "column_ordinal": len(pk_columns) + 1,
                }
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
                "fk_constraint_name": f"fk_{ct}_{cc}",
                "child_relation_oid": child,
                "parent_relation_oid": parent,
                "child_column_name": cc,
                "parent_column_name": pc,
                "column_ordinal": 1,
            }
        )

    columns_by_oid: dict[int, set[str]] = {}
    for column in columns:
        columns_by_oid.setdefault(column["relation_oid"], set()).add(
            column["column_name"]
        )
    used_names_by_schema: dict[str, set[str]] = {}
    for relation in relations:
        used_names_by_schema.setdefault(relation["schema_name"], set()).add(
            relation["relation_name"]
        )
    indexes: list[dict[str, Any]] = []
    for (
        schema,
        table,
    ), index_columns, unique, primary, method, explicit_name, ordinal in index_specs:
        relation_oid = oid_by_table.get((schema, table))
        if relation_oid is None or not set(index_columns).issubset(
            columns_by_oid.get(relation_oid, set())
        ):
            continue
        if primary:
            existing_pk = [
                pk
                for pk in pk_columns
                if pk["relation_oid"] == relation_oid
            ]
            if not existing_pk:
                for position, column_name in enumerate(index_columns, start=1):
                    pk_columns.append(
                        {
                            "relation_oid": relation_oid,
                            "column_name": column_name,
                            "column_ordinal": position,
                        }
                    )
                    for column in columns:
                        if (
                            column["relation_oid"] == relation_oid
                            and column["column_name"] == column_name
                        ):
                            column["is_not_null"] = True
                            break
            continue
        base_name = explicit_name or f"ix_{table}_{'_'.join(index_columns)}"
        name = _index_name(base_name, ordinal, preserve=explicit_name is not None)
        used_names = used_names_by_schema.setdefault(schema, set())
        suffix_ordinal = ordinal
        while name in used_names:
            name = _index_name(base_name, suffix_ordinal)
            suffix_ordinal += 1
        used_names.add(name)
        quoted_columns = ", ".join(
            _quote_identifier(column) for column in index_columns
        )
        indexes.append(
            {
                "relation_oid": relation_oid,
                "table_oid": relation_oid,
                "index_name": name,
                "access_method": method,
                "access_method_extension": None,
                "operator_class_extensions": [],
                "is_unique": unique,
                "is_primary": primary,
                "is_valid": True,
                "predicate_expr": None,
                "index_tablespace_name": None,
                "index_def": (
                    f"CREATE {'UNIQUE ' if unique else ''}INDEX {_quote_identifier(name)} "
                    f"ON {_quote_identifier(schema)}.{_quote_identifier(table)} "
                    f"USING {method} ({quoted_columns})"
                ),
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
