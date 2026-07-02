from __future__ import annotations

import importlib.util
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "commercial_readiness_audit.py"


def load_audit() -> Any:
    assert SCRIPT.is_file(), "commercial readiness audit script is missing"
    spec = importlib.util.spec_from_file_location("commercial_readiness_audit", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_report_flags_example_only_evidence() -> None:
    audit = load_audit()

    report = audit.generate_report()

    assert report["schema_ready"] is True
    assert report["real_evidence_ready"] is False
    assert report["sale_ready"] is False
    no_go_ids = {
        gate["id"]
        for gate in report["real_evidence_gates"]
        if gate["status"] == "no_go"
    }
    assert "signed_release_approval" in no_go_ids
    assert "real_billing_provider_catalog" in no_go_ids
    assert report["review_queue_is_blocker"] is False
    assert report["queued_checks_are_blocker"] is False


def test_strict_mode_fails_when_not_sale_ready() -> None:
    audit = load_audit()

    assert audit.main(["--strict"]) == 1


def test_report_can_write_json(tmp_path: pathlib.Path) -> None:
    audit = load_audit()
    output = tmp_path / "commercial-readiness-audit.json"

    assert audit.main(["--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"] == "not_ready_for_sale"
    assert payload["schema_ready"] is True
