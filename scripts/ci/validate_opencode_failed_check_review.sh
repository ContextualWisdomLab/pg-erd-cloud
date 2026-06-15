#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <control-json-file> <failed-checks-file> <failed-check-evidence-file>" >&2
  exit 64
fi

CONTROL_JSON_FILE="$1"
FAILED_CHECKS_FILE="$2"
FAILED_CHECK_EVIDENCE_FILE="$3"

if [ ! -r "$CONTROL_JSON_FILE" ] || [ ! -r "$FAILED_CHECKS_FILE" ] || [ ! -r "$FAILED_CHECK_EVIDENCE_FILE" ]; then
  echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
  exit 4
fi

if [ ! -s "$FAILED_CHECKS_FILE" ]; then
  exit 0
fi

review_text="$(
  jq -r '
    [
      (.summary // ""),
      (.reason // ""),
      (
        .findings[]?
        | [
            (.path // ""),
            ((.line // "") | tostring),
            (.severity // ""),
            (.title // ""),
            (.problem // ""),
            (.root_cause // ""),
            (.fix_direction // ""),
            (.regression_test_direction // ""),
            (.suggested_diff // "")
          ]
        | join("\n")
      )
    ]
    | join("\n")
  ' "$CONTROL_JSON_FILE"
)"

contains_review_text() {
  local needle="$1"
  if [ -z "$needle" ]; then
    return 0
  fi
  grep -Fqi -- "$needle" <<<"$review_text"
}

extract_strix_required_markers() {
  perl -CS -ne '
    s/\r//g;
    s/\x1b\[[0-9;?]*[A-Za-z]//g;
    if (/│/) {
      s/^.*?│[[:space:]]*//;
      s/[[:space:]]*│.*$//;
    } else {
      s/^.*?[0-9]Z[[:space:]]+//;
    }
    s/[[:space:]]+/ /g;
    s/^[[:space:]]+|[[:space:]]+$//g;

    if (/^Title:[[:space:]]+(.+)/) {
      print "$1\n";
    }
    if (/^Severity:[[:space:]]+(CRITICAL|HIGH|MEDIUM|LOW)\b/) {
      print "Severity: $1\n";
    }
    if (/^Endpoint:[[:space:]]+(.+)/) {
      print "$1\n";
    }
    if (/^Method:[[:space:]]+(.+)/) {
      print "Method: $1\n";
    }
    if (/^Location[[:space:]]+[0-9]+:[[:space:]]+(.+:[0-9]+(?:-[0-9]+)?)/) {
      print "$1\n";
    }
  ' "$FAILED_CHECK_EVIDENCE_FILE"
}

extract_strix_title_markers() {
  perl -CS -ne '
    s/\r//g;
    s/\x1b\[[0-9;?]*[A-Za-z]//g;
    if (/│/) {
      s/^.*?│[[:space:]]*//;
      s/[[:space:]]*│.*$//;
    } else {
      s/^.*?[0-9]Z[[:space:]]+//;
    }
    s/[[:space:]]+/ /g;
    s/^[[:space:]]+|[[:space:]]+$//g;
    if (/^Title:[[:space:]]+(.+)/) {
      print "$1\n";
    }
  ' "$FAILED_CHECK_EVIDENCE_FILE"
}

count_strix_review_findings() {
  jq -r '
    [
      (.findings // [])[]
      | [
          .title,
          .problem,
          .root_cause,
          .fix_direction,
          .regression_test_direction,
          .suggested_diff
        ]
        | map(. // "")
        | join("\n")
      | select(test("strix|github[-_]models/|deepseek/|openai/gpt-|vertex_ai/|Vulnerability Report"; "i"))
    ]
    | length
  ' "$CONTROL_JSON_FILE"
}

validate_distinct_strix_report_findings() {
  python3 - "$CONTROL_JSON_FILE" "$FAILED_CHECK_EVIDENCE_FILE" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


control_file = Path(sys.argv[1])
evidence_file = Path(sys.argv[2])
control = json.loads(control_file.read_text(encoding="utf-8"))
evidence_text = evidence_file.read_text(encoding="utf-8", errors="replace")

ansi_re = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
model_re = re.compile(
    r"(?:^|[\s])Model\s+((?:github[-_]models|openai|deepseek|vertex_ai)/[A-Za-z0-9._/-]+)",
    re.IGNORECASE,
)
failed_model_re = re.compile(r"Strix run failed for model '([^']+)'")
location_re = re.compile(
    r"(?:Code\s+)?Locations?(?:\s+[0-9]+)?\s*:\s*(.+?:[0-9]+(?:-[0-9]+)?)",
    re.IGNORECASE,
)


def clean(raw_line: str) -> str:
    line = ansi_re.sub("", raw_line).replace("\r", "")
    if "│" in line:
        line = re.sub(r"^.*?│\s*", "", line)
        line = re.sub(r"\s*│.*$", "", line)
    else:
        line = re.sub(r"^.*?[0-9]Z\s+", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def starts_new_field(line: str) -> bool:
    return bool(
        re.match(
            r"^(Title|Severity|CVSS Score|CVSS Vector|Target|Endpoint|Method|Description|Impact|Technical Analysis|PoC Description|PoC Code|Code Locations|Remediation)\b",
            line,
            re.IGNORECASE,
        )
    )


def parse_reports(text: str) -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    in_window = False
    window_model = ""
    current_model = ""
    report_model = ""
    title = ""
    severity = ""
    endpoint = ""
    method = ""
    target = ""
    location = ""
    continuation = ""

    def finish_report() -> None:
        nonlocal report_model, title, severity, endpoint, method, target, location
        if title:
            reports.append(
                {
                    "model": report_model or window_model or current_model or "unknown-model",
                    "title": title,
                    "severity": severity,
                    "endpoint": endpoint,
                    "method": method,
                    "target": target,
                    "location": location,
                }
            )
        report_model = title = severity = endpoint = method = target = location = ""

    for raw_line in text.splitlines():
        line = clean(raw_line)
        if line.lower().startswith("### strix vulnerability report window"):
            finish_report()
            in_window = True
            window_model = ""
            match = re.search(
                r"(?:model|for model)\s+((?:github[-_]models|openai|deepseek|vertex_ai)/[A-Za-z0-9._/-]+)",
                line,
                re.IGNORECASE,
            )
            if match:
                window_model = match.group(1)
                current_model = match.group(1)
            continuation = ""
            continue

        match = model_re.search(line) or failed_model_re.search(line)
        if match:
            current_model = match.group(1)
            if in_window and not window_model:
                window_model = current_model
            if title and not report_model:
                report_model = current_model

        if not in_window:
            continue

        if continuation:
            if not line:
                continuation = ""
            elif not starts_new_field(line) and not re.match(r"^[╭╰─]+$", line) and line.lower() != "vulnerability report":
                if continuation == "title":
                    title = f"{title} {line}".strip()
                elif continuation == "endpoint":
                    endpoint = f"{endpoint} {line}".strip()
                elif continuation == "target":
                    target = f"{target} {line}".strip()
                continue
            else:
                continuation = ""

        if line.lower() == "vulnerability report":
            continue
        field_match = re.match(r"^Title:\s+(.+)", line, re.IGNORECASE)
        if field_match:
            finish_report()
            title = field_match.group(1)
            report_model = window_model or current_model
            continuation = "title"
            continue
        field_match = re.match(r"^Severity:\s+(CRITICAL|HIGH|MEDIUM|LOW|NONE)\b", line, re.IGNORECASE)
        if field_match:
            severity = field_match.group(1).upper()
            continue
        field_match = re.match(r"^Endpoint:\s+(.+)", line, re.IGNORECASE)
        if field_match:
            endpoint = field_match.group(1)
            continuation = "endpoint"
            continue
        field_match = re.match(r"^Method:\s+(.+)", line, re.IGNORECASE)
        if field_match:
            method = field_match.group(1)
            continuation = ""
            continue
        field_match = re.match(r"^Target:\s+(.+)", line, re.IGNORECASE)
        if field_match:
            target = field_match.group(1)
            continuation = "target"
            continue
        field_match = location_re.search(line)
        if field_match and not location:
            location = field_match.group(1)

    finish_report()
    return [report for report in reports if report["title"] and report["severity"] != "NONE"]


def finding_text(finding: dict[str, object]) -> str:
    fields = [
        "path",
        "line",
        "severity",
        "title",
        "problem",
        "root_cause",
        "fix_direction",
        "regression_test_direction",
        "suggested_diff",
    ]
    return "\n".join(str(finding.get(field, "")) for field in fields).lower()


def contains(text: str, marker: str) -> bool:
    return not marker or marker.lower() in text


reports = parse_reports(evidence_text)
if not reports:
    raise SystemExit(0)

findings = [finding_text(finding) for finding in control.get("findings", []) if isinstance(finding, dict)]
used_findings: set[int] = set()

for report in reports:
    required_markers = [
        report["model"],
        report["title"],
        report["severity"],
        report["endpoint"],
        report["method"],
        report["location"],
    ]
    for index, text in enumerate(findings):
        if index in used_findings:
            continue
        if all(contains(text, marker) for marker in required_markers):
            used_findings.add(index)
            break
    else:
        raise SystemExit(1)
PY
}

while IFS= read -r failed_check_line; do
  case "$failed_check_line" in
    "- "*)
      failed_check_label="${failed_check_line#- }"
      failed_check_label="${failed_check_label%%:*}"
      if ! contains_review_text "$failed_check_label"; then
        echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
        exit 4
      fi
      ;;
  esac
done <"$FAILED_CHECKS_FILE"

while IFS= read -r fail_marker; do
  if ! contains_review_text "$fail_marker"; then
    echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
    exit 4
  fi
done < <(awk -F 'FAIL: ' 'NF > 1 { print $2 }' "$FAILED_CHECK_EVIDENCE_FILE" | sort -u)

for evidence_marker in \
  "Self-test Strix gate script" \
  "github.event.inputs.strix_llm" \
  "STRIX_LLM must select" \
  "MODEL: github-models/openai/gpt-5"
do
  if grep -Fq -- "$evidence_marker" "$FAILED_CHECK_EVIDENCE_FILE" &&
    ! contains_review_text "$evidence_marker"; then
    echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
    exit 4
  fi
done

if grep -Fq "Strix vulnerability report window" "$FAILED_CHECK_EVIDENCE_FILE"; then
  if ! validate_distinct_strix_report_findings; then
    echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
    exit 4
  fi

  strix_title_count="$(extract_strix_title_markers | sed '/^[[:space:]]*$/d' | wc -l | tr -d '[:space:]')"
  finding_count="$(count_strix_review_findings)"
  if [ -n "$strix_title_count" ] && [ "$strix_title_count" -gt 0 ] &&
    [ "$finding_count" -lt "$strix_title_count" ]; then
    echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
    exit 4
  fi

  while IFS= read -r model_name; do
    if ! contains_review_text "$model_name"; then
      echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
      exit 4
    fi
  done < <(
    perl -ne 'while (m{(?:openai|deepseek|vertex_ai|github(?:_|-)models)/[A-Za-z0-9._/-]+}g) { print "$&\n" }' \
      "$FAILED_CHECK_EVIDENCE_FILE" | sort -u
  )

  while IFS= read -r strix_marker; do
    if ! contains_review_text "$strix_marker"; then
      echo "FAILED_CHECK_EVIDENCE_NOT_REFERENCED"
      exit 4
    fi
  done < <(extract_strix_required_markers)
fi

exit 0
