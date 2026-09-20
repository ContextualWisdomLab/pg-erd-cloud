"""Regression coverage for the supported CI schema-drift auth contract."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts/ci/check_schema_drift.sh"


def test_schema_drift_script_requires_bearer_token() -> None:
    """The script must not advertise the unsupported session-cookie flow."""

    environment = os.environ.copy()
    environment["PG_ERD_BASE_URL"] = "https://erd.example.test"
    environment.pop("PG_ERD_TOKEN", None)
    environment.pop("PG_ERD_COOKIE", None)

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "baseline", "target"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 2
    assert "PG_ERD_TOKEN is not set" in result.stderr
    assert "PG_ERD_COOKIE" not in SCRIPT_PATH.read_text(encoding="utf-8")


def test_schema_drift_script_sends_token_as_authorization_header(
    tmp_path: Path,
) -> None:
    """A successful no-drift call uses Bearer auth without printing the token."""

    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
found=false
for ((index=1; index<=$#; index++)); do
  if [ "${!index}" = "--header" ]; then
    next=$((index + 1))
    if [ "${!next}" = "Authorization: Bearer contract-token" ]; then
      found=true
    fi
  fi
done
if [ "$found" != true ]; then
  exit 55
fi
printf '%s' '{"status":"ok","diff":{"summary":{"has_changes":false}}}'
""",
        encoding="utf-8",
    )
    fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)

    environment = os.environ.copy()
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"
    environment["PG_ERD_BASE_URL"] = "https://erd.example.test"
    environment["PG_ERD_TOKEN"] = "contract-token"

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "baseline", "target"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "schema matches" in result.stdout
    assert "contract-token" not in result.stdout
    assert "contract-token" not in result.stderr


def test_schema_drift_failure_does_not_print_reconciliation_sql() -> None:
    """CI logs must not receive schema comments or identifiers from generated SQL."""

    assert "migration.sql" not in SCRIPT_PATH.read_text(encoding="utf-8")
