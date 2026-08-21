#!/usr/bin/env python3
"""Atheris harness for the snapshot-driven spec/report generators.

Untrusted-input surface: the same DB-introspection *snapshot* is fed to several
pure generators that emit Markdown / LLM prompts / finding reports:

    app.spec.reversing.generate_reversing_spec
    app.spec.index_design.generate_index_design_spec
    app.spec.naming_lint.lint_naming
    app.spec.wide_tables.detect_wide_tables

Each must be total over arbitrary snapshot shapes (only an unsupported *mode*
may raise ``ValueError``) and deterministic. The report generators additionally
carry internal invariants (summary counts match the emitted items) that we
assert here.

CodeGraph pointed here via:
    codegraph explore "generate_reversing_spec index_design naming_lint snapshot"

Run: python backend/fuzz/fuzz_spec_generators.py backend/fuzz/corpus/reversing_spec
"""

from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from app.spec.index_design import generate_index_design_spec
    from app.spec.naming_lint import lint_naming
    from app.spec.reversing import generate_reversing_spec
    from app.spec.wide_tables import detect_wide_tables

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _snapshot import ByteFeeder, build_snapshot  # noqa: E402

_MODES = ["markdown", "llm-prompt", "bogus", ""]


def _check_str_spec(fn, snapshot, mode) -> None:
    try:
        out = fn(snapshot, mode)
    except ValueError:
        return  # unsupported mode is a documented error
    if not isinstance(out, str):
        raise AssertionError(f"{fn.__name__} returned {type(out)!r}, expected str")
    if out != fn(snapshot, mode):
        raise AssertionError(f"{fn.__name__} is non-deterministic")


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    feeder = ByteFeeder.from_fdp(fdp)
    snapshot = build_snapshot(feeder)
    mode = _MODES[fdp.ConsumeIntInRange(0, len(_MODES) - 1)]

    _check_str_spec(generate_reversing_spec, snapshot, mode)
    _check_str_spec(generate_index_design_spec, snapshot, mode)

    # naming_lint: report dict with self-consistent summary counts.
    report = lint_naming(snapshot)
    items = report["items"]
    summary = report["summary"]
    if summary["total"] != len(items):
        raise AssertionError("naming_lint summary total mismatch")
    high = sum(1 for i in items if i["severity"] == "high")
    info = sum(1 for i in items if i["severity"] == "info")
    if summary["high"] != high or summary["info"] != info:
        raise AssertionError("naming_lint summary severity counts mismatch")

    # wide_tables: never raises, returns a dict.
    wide = detect_wide_tables(snapshot)
    if not isinstance(wide, dict):
        raise AssertionError("detect_wide_tables did not return a dict")


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
