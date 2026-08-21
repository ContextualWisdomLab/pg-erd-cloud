"""Lint schema identifier names for things that actually break, not taste.

The standard here is deliberately objective:

1. **reserved_word** (high) -- the identifier is a SQL reserved keyword, so it
   only works when double-quoted; unquoted use is a syntax error / silent bug.
2. **requires_quoting** (high) -- the identifier isn't a legal *unquoted*
   PostgreSQL identifier (uppercase, space, hyphen, leading digit, > 63 chars).
   Postgres folds unquoted names to lower-case, so such a name only works if it
   was created quoted everywhere -- a footgun.
3. **inconsistent_case** (info) -- the identifier's case style differs from the
   schema's own dominant style (e.g. one camelCase name in a snake_case schema).
   No style is imposed; only self-consistency is measured.

Pure and dialect-agnostic (PostgreSQL identifier rules).
"""

from __future__ import annotations

import re
from typing import Any

HIGH = "high"
INFO = "info"
_SEVERITY_RANK = {HIGH: 0, INFO: 1}

# PostgreSQL fully-reserved key words (cannot be a table/column name unquoted).
RESERVED_WORDS = frozenset(
    """all analyse analyze and any array as asc asymmetric both case cast check
    collate column constraint create current_catalog current_date current_role
    current_time current_timestamp current_user default deferrable desc distinct
    do else end except false fetch for foreign from grant group having in
    initially intersect into lateral leading limit localtime localtimestamp not
    null offset on only or order placing primary references returning select
    session_user some symmetric table then to trailing true union unique user
    using variadic when where window with""".split()
)

# Non-reserved keywords / built-in type names: legal as unquoted identifiers,
# but they shadow a keyword/type and routinely confuse tooling and readers.
DISCOURAGED_KEYWORDS = frozenset(
    """name value type text timestamp date time number comment level position
    path language role owner zone source target state key day month year hour
    minute second precision boolean integer char character interval money""".split()
)

_VALID_UNQUOTED = re.compile(r"^[a-z_][a-z0-9_$]*$")


def _rows(snapshot: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return ``snapshot[key]`` as dict rows, tolerating malformed JSON.

    A key that is missing, not a list, or holds non-dict entries degrades to
    "no rows" rather than raising -- the same defensive contract used by the
    other snapshot generators (``app.spec.reversing._rows`` etc.).
    """

    value = snapshot.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _case_style(name: str) -> str | None:
    """Classify identifier case style, or None if it can't be classified."""
    if re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name):
        return "snake"
    if re.fullmatch(r"[a-z][a-zA-Z0-9]*", name) and any(c.isupper() for c in name):
        return "camel"
    if re.fullmatch(r"[A-Z][a-zA-Z0-9]*", name):
        return "pascal"
    return None


def _item(category: str, severity: str, target: str, detail: str) -> dict[str, Any]:
    return {"category": category, "severity": severity, "target": target, "detail": detail}


def lint_naming(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return naming-convention findings + a summary, breaking issues first."""
    snapshot = snapshot or {}
    relations = _rows(snapshot, "relations")
    columns = _rows(snapshot, "columns")
    rel_by_oid = {r.get("relation_oid"): r for r in relations}

    # (label, name) for every identifier: tables and columns.
    identifiers: list[tuple[str, str]] = []
    for r in relations:
        name = r.get("relation_name")
        if name:
            identifiers.append((f"{r.get('schema_name')}.{name}", str(name)))
    for c in columns:
        name = c.get("column_name")
        if name:
            rel = rel_by_oid.get(c.get("relation_oid")) or {}
            identifiers.append((f"{rel.get('relation_name')}.{name}", str(name)))

    items: list[dict[str, Any]] = []
    styles: dict[str, int] = {}

    for label, name in identifiers:
        lower = name.lower()
        if lower in RESERVED_WORDS:
            items.append(
                _item("reserved_word", HIGH, label,
                      f"'{name}' is a SQL reserved word — only usable double-quoted; unquoted use breaks.")
            )
        elif not _VALID_UNQUOTED.match(name) or len(name) > 63:
            items.append(
                _item("requires_quoting", HIGH, label,
                      f"'{name}' is not a legal unquoted identifier (case/char/length) — forces double-quoting everywhere.")
            )
        elif lower in DISCOURAGED_KEYWORDS:
            items.append(
                _item("discouraged_keyword", INFO, label,
                      f"'{name}' is a non-reserved keyword / type name — legal unquoted, but shadows a keyword and confuses tooling.")
            )
        style = _case_style(name)
        if style is not None:
            styles[style] = styles.get(style, 0) + 1

    # Consistency: only flag outliers when there is a clear dominant style.
    total_styled = sum(styles.values())
    dominant = max(styles, key=lambda s: styles[s]) if styles else None
    if dominant and total_styled >= 4 and styles[dominant] / total_styled >= 0.6:
        for label, name in identifiers:
            style = _case_style(name)
            if style is not None and style != dominant:
                items.append(
                    _item("inconsistent_case", INFO, label,
                          f"'{name}' is {style}, but the schema is predominantly {dominant}.")
                )

    items.sort(key=lambda i: (_SEVERITY_RANK.get(i["severity"], 9), i["target"]))

    summary = {
        "high": sum(1 for i in items if i["severity"] == HIGH),
        "info": sum(1 for i in items if i["severity"] == INFO),
        "total": len(items),
        "dominant_case": dominant,
    }
    return {"items": items, "summary": summary}
