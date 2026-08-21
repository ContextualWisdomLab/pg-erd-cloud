"""Flag columns that likely hold sensitive / personal data (PII).

This is a compliance **scoping** aid, NOT enforcement. It answers "which columns
put me in regulatory scope?" by mapping likely-sensitive columns to the relevant
framework (PCI DSS for card data, GDPR/PIPA for personal & special-category
data, secrets-management for credentials). It does NOT encrypt, mask, tokenize,
or apply access controls -- that remediation is the database owner's job.

Pure and dialect-agnostic; name-heuristic only (no data is read). ponytail:
name matching flags likely locations -- a review starting point, not proof; it
won't catch sensitive data hidden behind an opaque column name, nor confirm a
matched column actually holds regulated data.
"""

from __future__ import annotations

import re
from typing import Any

HIGH = "high"
MEDIUM = "medium"
LOW = "low"

_SEVERITY_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2}

# (category, severity, framework, compiled pattern). Order matters: first match
# wins, so the most specific / most sensitive categories come first. `framework`
# names the regulation that brings the column into scope.
_RULES: list[tuple[str, str, str, re.Pattern[str]]] = [
    ("credential", HIGH, "Secrets (must never be stored in plaintext)", re.compile(r"pass(word|wd)?|passwd|secret|api[_-]?key|token|private[_-]?key|salt|otp")),
    ("national_id", HIGH, "GDPR Art.9 / PIPA unique-identifier & special category", re.compile(r"ssn|social[_-]?security|resident[_-]?reg|jumin|national[_-]?id|passport|tax[_-]?id|driver[_-]?licen"),),
    ("payment", HIGH, "PCI DSS (cardholder data environment)", re.compile(r"card[_-]?(no|num|number)|credit[_-]?card|ccnum|cvv|cvc|iban|account[_-]?(no|number)|routing")),
    ("special_category", HIGH, "GDPR Art.9 / PIPA sensitive data", re.compile(r"(^|_)health|medical|diagnos|disease|biometric|fingerprint|(^|_)race($|_)|ethnic|religion|political|sexual|genetic")),
    ("contact", MEDIUM, "GDPR / PIPA personal data", re.compile(r"e[_-]?mail|(^|_)email|phone|mobile|(^|_)tel($|_)|fax")),
    ("location", MEDIUM, "GDPR / PIPA personal data", re.compile(r"address|(^|_)addr($|_)|zip[_-]?code|postal|(^|_)city($|_)|latitude|longitude|(^|_)geo")),
    ("personal", MEDIUM, "GDPR / PIPA personal data", re.compile(r"birth|(^|_)dob($|_)|gender|nationality|marital")),
    ("name", LOW, "GDPR / PIPA personal data", re.compile(r"(first|last|full|middle|given|family)[_-]?name|(^|_)fname|(^|_)lname|username|nickname")),
]


def detect_sensitive_columns(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return a classified inventory of likely-sensitive columns."""
    snapshot = snapshot or {}
    relations = snapshot.get("relations") or []
    columns = snapshot.get("columns") or []

    rel_by_oid = {r.get("relation_oid"): r for r in relations}
    items: list[dict[str, Any]] = []

    for col in columns:
        name = str(col.get("column_name") or "")
        if not name:
            continue
        lname = name.lower()
        for category, severity, framework, pattern in _RULES:
            if pattern.search(lname):
                rel = rel_by_oid.get(col.get("relation_oid")) or {}
                items.append(
                    {
                        "schema": rel.get("schema_name"),
                        "table": rel.get("relation_name"),
                        "column": name,
                        "category": category,
                        "severity": severity,
                        "framework": framework,
                    }
                )
                break  # first (most sensitive) match wins

    items.sort(
        key=lambda i: (
            _SEVERITY_RANK.get(i["severity"], 9),
            str(i["schema"]),
            str(i["table"]),
            str(i["column"]),
        )
    )

    by_framework: dict[str, int] = {}
    for i in items:
        by_framework[i["framework"]] = by_framework.get(i["framework"], 0) + 1

    summary = {
        "high": sum(1 for i in items if i["severity"] == HIGH),
        "medium": sum(1 for i in items if i["severity"] == MEDIUM),
        "low": sum(1 for i in items if i["severity"] == LOW),
        "total": len(items),
        "by_framework": by_framework,
    }
    return {"items": items, "summary": summary}
