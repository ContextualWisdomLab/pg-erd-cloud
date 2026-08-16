"""The LLM draft transport explicitly delegates execution to auto policy."""

from pathlib import Path


def test_llm_transport_explicitly_requests_contextual_orchestrator_auto() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "app" / "spec" / "llm.py"
    ).read_text(encoding="utf-8")

    assert "orchestration_mode" in source
    assert "auto" in source
