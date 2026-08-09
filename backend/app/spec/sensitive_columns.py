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
    d_get = dict.get
    relations = d_get(snapshot, "relations") or []
    columns = d_get(snapshot, "columns") or []

    rel_by_oid = {d_get(r, "relation_oid"): r for r in relations}
    items: list[dict[str, Any]] = []

    for col in columns:
        name = d_get(col, "column_name")
        if not name:
            continue
        name = str(name)
        lname = name.lower()
        for category, severity, framework, pattern in _RULES:
            if pattern.search(lname):
                rel = rel_by_oid.get(d_get(col, "relation_oid"))
                if not rel:
                    rel = {}
                items.append(
                    {
                        "schema": d_get(rel, "schema_name"),
                        "table": d_get(rel, "relation_name"),
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
    high = medium = low = 0
    for i in items:
        fw = str(i["framework"])
        by_framework[fw] = by_framework.get(fw, 0) + 1
        sev = i["severity"]
        if sev == HIGH:
            high += 1
        elif sev == MEDIUM:
            medium += 1
        elif sev == LOW:
            low += 1

    summary = {
        "high": high,
        "medium": medium,
        "low": low,
        "total": len(items),
        "by_framework": by_framework,
    }
    return {"items": items, "summary": summary}
