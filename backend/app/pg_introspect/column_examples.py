from __future__ import annotations


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _normalized(value: object) -> str:
    return _text(value).strip().lower()


def _has_name(column_name: str, *patterns: str) -> bool:
    return any(pattern in column_name for pattern in patterns)


def infer_column_example(column: dict) -> str:
    """Infer a synthetic example value from column metadata.

    The value is intentionally generated from names and types only. Do not read
    live table data here; snapshots are shareable and should not capture PII.
    """

    column_name = _normalized(column.get("column_name"))
    data_type = _normalized(column.get("data_type"))
    type_name = _normalized(column.get("type_name"))
    type_category = _normalized(column.get("type_category"))
    type_kind = _normalized(column.get("type_kind"))
    combined_type = f"{data_type} {type_name}"

    if _has_name(column_name, "email", "e_mail") or column_name == "mail":
        return "user@example.com"
    if _has_name(column_name, "phone", "mobile", "tel_no", "telephone"):
        return "+82-10-1234-5678"
    if _has_name(column_name, "url", "uri", "website", "homepage"):
        return "https://example.com/resource"
    if _has_name(column_name, "currency"):
        return "KRW"
    if _has_name(column_name, "country"):
        return "KR"
    if _has_name(column_name, "locale", "language"):
        return "ko-KR"
    if _has_name(column_name, "status", "state"):
        return "active"
    if _has_name(column_name, "category", "kind", "type"):
        return "standard"
    if _has_name(column_name, "code"):
        return "EXAMPLE_CODE"
    if _has_name(column_name, "city"):
        return "Seoul"
    if _has_name(column_name, "address"):
        return "123 Example St"
    if _has_name(column_name, "name", "title"):
        return "Example Name"
    if _has_name(column_name, "description", "comment", "memo", "note"):
        return "Example description"

    if (
        "uuid" in combined_type
        or column_name == "uuid"
        or column_name.endswith("_uuid")
    ):
        return "550e8400-e29b-41d4-a716-446655440000"
    if column_name == "id" or column_name.endswith("_id"):
        if "char" in combined_type or "text" in combined_type:
            return "ID-1001"
        return "1001"

    if "bool" in combined_type or type_category == "b":
        return "true"
    if "timestamp" in combined_type or _has_name(
        column_name, "created_at", "updated_at", "deleted_at"
    ):
        return "2026-01-15T09:30:00Z"
    if "date" in combined_type:
        return "2026-01-15"
    if "time" in combined_type:
        return "09:30:00"
    if "json" in combined_type:
        return '{"key":"value"}'
    if "bytea" in combined_type:
        return "base64:ZXhhbXBsZQ=="
    if any(network_type in combined_type for network_type in ("inet", "cidr")):
        return "192.0.2.10"
    if "macaddr" in combined_type:
        return "00:00:5e:00:53:01"
    if "interval" in combined_type:
        return "P1D"
    if type_category == "a" or data_type.endswith("[]"):
        return '["example"]'
    if type_kind == "e":
        return "example_value"
    if any(
        numeric_type in combined_type
        for numeric_type in (
            "int",
            "numeric",
            "decimal",
            "real",
            "double",
            "money",
        )
    ):
        if _has_name(column_name, "amount", "price", "cost", "total"):
            return "123.45"
        if _has_name(column_name, "rate", "ratio", "percent"):
            return "0.15"
        if _has_name(column_name, "count", "qty", "quantity"):
            return "10"
        return "123"
    if any(text_type in combined_type for text_type in ("char", "text", "citext")):
        return "example text"

    return "example"


def add_column_examples(columns: list[dict]) -> list[dict]:
    """Return copied column dictionaries with generated examples when missing."""
    enriched: list[dict] = []
    for column in columns:
        next_column = dict(column)
        next_column.setdefault("example_value", infer_column_example(next_column))
        next_column.setdefault("example_value_source", "generated")
        enriched.append(next_column)
    return enriched
