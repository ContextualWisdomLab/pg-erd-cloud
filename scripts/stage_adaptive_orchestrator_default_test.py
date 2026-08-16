#!/usr/bin/env python3
"""Stage a contract test for the pg-erd-cloud orchestration request default."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
test_path = root / "backend" / "tests" / "test_contextual_orchestrator_auto_default.py"
content = '''"""The LLM draft transport explicitly delegates execution to auto policy."""

from pathlib import Path


def test_llm_transport_explicitly_requests_contextual_orchestrator_auto() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "app" / "spec" / "llm.py"
    ).read_text(encoding="utf-8")

    assert "orchestration_mode" in source
    assert "auto" in source
'''

if test_path.exists():
    if test_path.read_text(encoding="utf-8") != content:
        raise SystemExit(f"refusing to replace a different test: {test_path}")
else:
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(content, encoding="utf-8")
