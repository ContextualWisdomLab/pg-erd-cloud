from __future__ import annotations

from app.spec.sensitive_columns import detect_sensitive_columns


def _snap(columns):
    return {
        "relations": [{"relation_oid": 1, "schema_name": "public", "relation_name": "member"}],
        "columns": [{"relation_oid": 1, "column_name": c} for c in columns],
    }


def _by_col(report):
    return {i["column"]: (i["category"], i["severity"]) for i in report["items"]}


def test_classifies_common_sensitive_columns():
    report = detect_sensitive_columns(
        _snap(["password_hash", "ssn", "credit_card_no", "email", "home_address", "date_of_birth", "first_name"])
    )
    byc = _by_col(report)
    assert byc["password_hash"] == ("credential", "high")
    assert byc["ssn"] == ("national_id", "high")
    assert byc["credit_card_no"] == ("payment", "high")
    assert byc["email"] == ("contact", "medium")
    assert byc["home_address"] == ("location", "medium")
    assert byc["date_of_birth"] == ("personal", "medium")
    assert byc["first_name"] == ("name", "low")


def test_ignores_plain_columns_and_sorts_high_first():
    report = detect_sensitive_columns(_snap(["id", "created_at", "quantity", "email", "api_key"]))
    cols = _by_col(report)
    assert "id" not in cols and "quantity" not in cols
    severities = [i["severity"] for i in report["items"]]
    assert severities == sorted(severities, key={"high": 0, "medium": 1, "low": 2}.get)
    assert report["summary"]["high"] == 1  # api_key


def test_maps_findings_to_compliance_frameworks():
    report = detect_sensitive_columns(_snap(["card_number", "email", "medical_history"]))
    fw = {i["column"]: i["framework"] for i in report["items"]}
    assert "PCI DSS" in fw["card_number"]
    assert "GDPR" in fw["email"]
    assert "sensitive" in fw["medical_history"].lower()  # special category
    # per-framework breakdown lets a user answer "what is in PCI DSS scope?"
    assert report["summary"]["by_framework"]["PCI DSS (cardholder data environment)"] == 1


def test_first_most_sensitive_match_wins():
    # a column matching multiple rules is classified by the most sensitive one
    report = detect_sensitive_columns(_snap(["account_password"]))
    assert _by_col(report)["account_password"][0] == "credential"


def test_empty_snapshot():
    assert detect_sensitive_columns({})["items"] == []
    assert detect_sensitive_columns(None)["summary"]["total"] == 0
