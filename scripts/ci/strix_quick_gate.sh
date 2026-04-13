#!/usr/bin/env bash
# strix_quick_gate.sh — CI gate that runs Strix security scans with
# automatic model fallback, transient-error retry, and severity-based
# pass/fail decisions.
#
# STRIX_LOG is a per-attempt temp file consumed only by
# is_transient_same_model_retry_error(); cumulative report dirs in
# STRIX_REPORTS_DIR are never overwritten.  Refer to ARCHITECTURE.md
# for the 3-tier timeout classification hierarchy.
set -euo pipefail

SCRIPT_DIR="$({ CDPATH='' && cd -P -- "$(dirname -- "$0")" && pwd -P; })"
REPO_ROOT="$({ CDPATH='' && cd -P -- "$SCRIPT_DIR/../.." && pwd -P; })"
RAW_TARGET_PATH="${STRIX_TARGET_PATH:-./}"
TARGET_PATH=""
RAW_SCAN_MODE="${STRIX_SCAN_MODE:-quick}"
SCAN_MODE=""
ARTIFACT_REPORTS_DIR_RAW="${STRIX_REPORTS_DIR:-strix_runs}"
case "$ARTIFACT_REPORTS_DIR_RAW" in
  /*) ARTIFACT_REPORTS_DIR="$ARTIFACT_REPORTS_DIR_RAW" ;;
  *) ARTIFACT_REPORTS_DIR="$REPO_ROOT/$ARTIFACT_REPORTS_DIR_RAW" ;;
esac
STRIX_RUNTIME_DIR="$(mktemp -d "${TMPDIR:-/tmp}/strix-runtime.XXXXXX")"
STRIX_LOG="$STRIX_RUNTIME_DIR/strix.log"
ACTIVE_REPORTS_DIR="$STRIX_RUNTIME_DIR/reports"
STRIX_REPORTS_DIR="$ACTIVE_REPORTS_DIR"
STRIX_PROCESS_TIMEOUT_SECONDS="${STRIX_PROCESS_TIMEOUT_SECONDS:-1200}"
STRIX_TOTAL_TIMEOUT_SECONDS="${STRIX_TOTAL_TIMEOUT_SECONDS:-0}"
STRIX_PR_SCOPE_MAX_FILES_PER_BATCH="${STRIX_PR_SCOPE_MAX_FILES_PER_BATCH:-20}"
# shellcheck disable=SC2034  # consumed by sourced normalize_model helper
DEFAULT_PROVIDER_RAW="${STRIX_LLM_DEFAULT_PROVIDER:-}"
DEFAULT_PROVIDER=""
ORIGINAL_LLM_API_BASE="${LLM_API_BASE:-}"
STRIX_TRANSIENT_RETRY_PER_MODEL="${STRIX_TRANSIENT_RETRY_PER_MODEL:-0}"
STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS="${STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS:-3}"
STRIX_FAIL_ON_MIN_SEVERITY="${STRIX_FAIL_ON_MIN_SEVERITY:-CRITICAL}"
RUN_START_EPOCH="$(date +%s)"
PREEXISTING_REPORT_DIRS=()
REPO_NAME="${REPO_ROOT##*/}"
# shellcheck source=scripts/ci/strix_model_utils.sh
. "$SCRIPT_DIR/strix_model_utils.sh"
# Sticky flag: once ANY attempt encounters an infrastructure error (rate limit,
# LLM connection failure, mid-stream fallback, etc.), this flag stays 1 for
# the rest of the run.  It prevents the "all findings below threshold" bypass
# from masking scan incompleteness — a successful strix run (exit 0) ignores
# this flag because the scan itself produced a complete result set.
INFRA_ERROR_DETECTED=0
PR_FINDINGS_DECISION="not_applicable"
CHANGED_FILES=()
PULL_REQUEST_SCOPE_DIRS=()
PULL_REQUEST_SCOPE_FILE_BATCHES=()
CURRENT_PULL_REQUEST_BATCH_FILE_COUNT=0
LAST_PULL_REQUEST_SCOPE_DIR=""

# shellcheck disable=SC2317,SC2329  # invoked from cleanup trap
publish_artifact_reports() {
  if [ -L "$ARTIFACT_REPORTS_DIR" ]; then
    echo "ERROR: artifact reports path must not be a symlink: $ARTIFACT_REPORTS_DIR" >&2
    return 1
  fi
  rm -rf "$ARTIFACT_REPORTS_DIR"
  mkdir -p "$ARTIFACT_REPORTS_DIR"
  if [ -d "$ACTIVE_REPORTS_DIR" ]; then
    cp -R "$ACTIVE_REPORTS_DIR"/. "$ARTIFACT_REPORTS_DIR"/
  fi
}

# shellcheck disable=SC2317,SC2329  # invoked from EXIT/INT/TERM trap
cleanup_runtime() {
  publish_artifact_reports || true
  rm -f "$STRIX_LOG"
  rm -rf "$STRIX_RUNTIME_DIR"
  local scope_dir
  for scope_dir in "${PULL_REQUEST_SCOPE_DIRS[@]}"; do
    if [ -n "$scope_dir" ] && [ -d "$scope_dir" ]; then
      rm -rf "$scope_dir"
    fi
  done
}

trap cleanup_runtime EXIT INT TERM

STRIX_LLM="$(trim_whitespace "${STRIX_LLM:-}")"
if [ -z "$STRIX_LLM" ]; then
  echo "ERROR: STRIX_LLM is required." >&2
  exit 2
fi

LLM_API_KEY="$(trim_whitespace "${LLM_API_KEY:-}")"
if [ -z "$LLM_API_KEY" ]; then
  echo "ERROR: LLM_API_KEY is required." >&2
  exit 2
fi

require_non_negative_integer() {
  local value="$1"
  local label="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "ERROR: $label must be a non-negative integer, got '$value'." >&2
    exit 2
  fi
}

require_positive_integer() {
  local value="$1"
  local label="$2"
  require_non_negative_integer "$value" "$label"
  if [ "$value" -le 0 ]; then
    echo "ERROR: $label must be greater than zero, got '$value'." >&2
    exit 2
  fi
  return 0
}

require_safe_scan_mode() {
  local scan_mode="$1"
  if [ -z "$scan_mode" ] || [[ ! "$scan_mode" =~ ^[[:alnum:]_.-]+$ ]]; then
    echo "ERROR: STRIX_SCAN_MODE contains unsupported characters: '$scan_mode'." >&2
    exit 2
  fi
}

is_supported_source_file() {
  case "$1" in
    *.java | *.kt | *.kts | *.groovy | *.scala | *.py | *.js | *.jsx | *.ts | *.tsx | *.vue | *.yaml | *.yml | *.sh | *.sql | *.xml | *.json | *.md)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

severity_rank() {
  case "${1^^}" in
    CRITICAL)
      echo 4
      ;;
    HIGH)
      echo 3
      ;;
    MEDIUM)
      echo 2
      ;;
    LOW)
      echo 1
      ;;
    INFO | INFORMATIONAL | NONE)
      echo 0
      ;;
    *)
      echo -1
      ;;
  esac
}

capture_preexisting_report_dirs() {
  local run_dir
  for run_dir in "$STRIX_REPORTS_DIR"/*; do
    if [ ! -d "$run_dir" ]; then
      continue
    fi
    PREEXISTING_REPORT_DIRS+=("$run_dir")
  done
}

is_preexisting_report_dir() {
  local candidate="$1"
  local existing

  for existing in "${PREEXISTING_REPORT_DIRS[@]}"; do
    if [ "$candidate" = "$existing" ]; then
      return 0
    fi
  done

  return 1
}

if ! DEFAULT_PROVIDER="$(sanitize_provider_name "$DEFAULT_PROVIDER_RAW")"; then
  exit 2
fi

PRIMARY_MODEL="$(normalize_model "$STRIX_LLM")"
if [ "$PRIMARY_MODEL" != "$STRIX_LLM" ]; then
  echo "Normalized STRIX_LLM to provider-qualified model '$PRIMARY_MODEL'."
fi

require_non_negative_integer "$STRIX_TRANSIENT_RETRY_PER_MODEL" "STRIX_TRANSIENT_RETRY_PER_MODEL"
require_non_negative_integer "$STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS" "STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS"
require_non_negative_integer "$STRIX_PROCESS_TIMEOUT_SECONDS" "STRIX_PROCESS_TIMEOUT_SECONDS"
require_non_negative_integer "$STRIX_TOTAL_TIMEOUT_SECONDS" "STRIX_TOTAL_TIMEOUT_SECONDS"
require_positive_integer "$STRIX_PR_SCOPE_MAX_FILES_PER_BATCH" "STRIX_PR_SCOPE_MAX_FILES_PER_BATCH"

if [ "$(severity_rank "$STRIX_FAIL_ON_MIN_SEVERITY")" -lt 0 ]; then
  echo "ERROR: STRIX_FAIL_ON_MIN_SEVERITY must be one of CRITICAL/HIGH/MEDIUM/LOW/INFO/INFORMATIONAL/NONE, got '$STRIX_FAIL_ON_MIN_SEVERITY'." >&2
  exit 2
fi

remaining_total_budget() {
  if [ "$STRIX_TOTAL_TIMEOUT_SECONDS" -eq 0 ]; then
    echo 0
    return 0
  fi

  local now elapsed remaining
  now="$(date +%s)"
  elapsed=$((now - RUN_START_EPOCH))
  remaining=$((STRIX_TOTAL_TIMEOUT_SECONDS - elapsed))
  if [ "$remaining" -lt 0 ]; then
    remaining=0
  fi
  echo "$remaining"
}

capture_preexisting_report_dirs

github_event_payload_has_pull_request() {
  if [ "${STRIX_CHANGED_FILES+x}" = x ] || { [ -n "${PR_BASE_SHA:-}" ] && [ -n "${PR_HEAD_SHA:-}" ]; }; then
    return 0
  fi
  if [ -z "${GITHUB_EVENT_PATH:-}" ] || [ ! -f "$GITHUB_EVENT_PATH" ]; then
    return 1
  fi
  python3 - "$GITHUB_EVENT_PATH" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    payload = json.load(fh)
pull_request = payload.get('pull_request') or {}
base = ((pull_request.get('base') or {}).get('sha')) or ''
head = ((pull_request.get('head') or {}).get('sha')) or ''
raise SystemExit(0 if base and head else 1)
PY
}

is_pull_request_event() {
  case "${GITHUB_EVENT_NAME:-}" in
    pull_request | pull_request_target)
      github_event_payload_has_pull_request
      ;;
    *)
      return 1
      ;;
  esac
}

path_is_within_allowed_scope() {
  local resolved_target="$1"
  case "$resolved_target" in
    "$REPO_ROOT" | "$REPO_ROOT"/*)
      return 0
      ;;
  esac

  local scope_dir
  for scope_dir in "${PULL_REQUEST_SCOPE_DIRS[@]}"; do
    scope_dir="$({ CDPATH='' && cd -P -- "$scope_dir" && pwd -P; })"
    case "$resolved_target" in
      "$scope_dir" | "$scope_dir"/*)
        return 0
        ;;
    esac
  done

  return 1
}

resolve_scan_target_path() {
  local raw_target="$1"
  local resolved_target
  resolved_target="$({
    python3 - "$REPO_ROOT" "$raw_target" <<'PY'
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve(strict=True)
raw_target = sys.argv[2]
target_path = Path(raw_target)
if not target_path.is_absolute():
    target_path = repo_root / target_path

resolved = target_path.resolve(strict=True)
print(resolved)
PY
  })" || {
    echo "ERROR: STRIX_TARGET_PATH '$raw_target' must resolve to an existing directory." >&2
    return 2
  }
  if [ ! -d "$resolved_target" ] || [ -L "$resolved_target" ]; then
    echo "ERROR: STRIX_TARGET_PATH '$raw_target' must resolve to a real directory." >&2
    return 2
  fi
  if ! path_is_within_allowed_scope "$resolved_target"; then
    echo "ERROR: STRIX_TARGET_PATH '$raw_target' must stay within the repository or generated PR scope directories." >&2
    return 2
  fi
  printf '%s\n' "$resolved_target"
}

SCAN_MODE="$(trim_whitespace "$RAW_SCAN_MODE")"
require_safe_scan_mode "$SCAN_MODE"
if ! TARGET_PATH="$(resolve_scan_target_path "$RAW_TARGET_PATH")"; then
  exit 2
fi

load_pull_request_changed_files() {
  CHANGED_FILES=()

  if [ "${STRIX_CHANGED_FILES+x}" = x ]; then
    while IFS= read -r changed_file; do
      changed_file="$(trim_whitespace "$changed_file")"
      if [ -n "$changed_file" ]; then
        CHANGED_FILES+=("$changed_file")
      fi
    done <<<"$STRIX_CHANGED_FILES"
    return 0
  fi

  if ! is_pull_request_event; then
    return 1
  fi

  local base_sha head_sha
  base_sha="$(trim_whitespace "${PR_BASE_SHA:-}")"
  head_sha="$(trim_whitespace "${PR_HEAD_SHA:-}")"
  if [ -z "$base_sha" ] || [ -z "$head_sha" ]; then
    if [ -z "${GITHUB_EVENT_PATH:-}" ] || [ ! -f "$GITHUB_EVENT_PATH" ]; then
      return 1
    fi

    local pr_shas
    pr_shas="$(
      python3 - "$GITHUB_EVENT_PATH" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as fh:
    payload = json.load(fh)
pull_request = payload.get('pull_request') or {}
base = ((pull_request.get('base') or {}).get('sha')) or ''
head = ((pull_request.get('head') or {}).get('sha')) or ''
print(base)
print(head)
PY
    )"
    base_sha="$(printf '%s' "$pr_shas" | sed -n '1p')"
    head_sha="$(printf '%s' "$pr_shas" | sed -n '2p')"
  fi
  if [ -z "$base_sha" ] || [ -z "$head_sha" ]; then
    return 1
  fi
  if ! git cat-file -e "$base_sha^{commit}" 2>/dev/null; then
    return 1
  fi
  if ! git cat-file -e "$head_sha^{commit}" 2>/dev/null; then
    return 1
  fi

  while IFS= read -r changed_file; do
    changed_file="$(trim_whitespace "$changed_file")"
    if [ -n "$changed_file" ]; then
      CHANGED_FILES+=("$changed_file")
    fi
  done < <(git diff --name-only "$base_sha" "$head_sha")

  [ "${#CHANGED_FILES[@]}" -gt 0 ]
}

is_scannable_changed_file() {
  local changed_file="$1"
  changed_file="$(trim_whitespace "$changed_file")"
  if [ -z "$changed_file" ]; then
    return 1
  fi
  if [[ "$changed_file" == */ ]]; then
    return 1
  fi
  if ! is_supported_source_file "$changed_file"; then
    return 1
  fi
  if [ ! -f "$REPO_ROOT/$changed_file" ] || [ -L "$REPO_ROOT/$changed_file" ]; then
    return 1
  fi
  return 0
}

build_pull_request_scope_dir() {
  local scope_dir
  scope_dir="$(mktemp -d "${TMPDIR:-/tmp}/strix-pr-scope.XXXXXX")"
  scope_dir="$({ CDPATH='' && cd -P -- "$scope_dir" && pwd -P; })"
  PULL_REQUEST_SCOPE_DIRS+=("$scope_dir")

  local changed_file
  for changed_file in "$@"; do
    mkdir -p "$scope_dir/$(dirname "$changed_file")"
    cp "$REPO_ROOT/$changed_file" "$scope_dir/$changed_file"
  done
  LAST_PULL_REQUEST_SCOPE_DIR="$scope_dir"
}

prepare_pull_request_scan_scope() {
  if ! is_pull_request_event; then
    return 0
  fi

  if ! load_pull_request_changed_files; then
    return 0
  fi

  local scoped_changed_files=()
  local changed_file
  for changed_file in "${CHANGED_FILES[@]}"; do
    if is_scannable_changed_file "$changed_file"; then
      scoped_changed_files+=("$changed_file")
    fi
  done

  if [ "${#scoped_changed_files[@]}" -eq 0 ]; then
    echo "No scannable changed files in pull request; skipping Strix quick scan." >&2
    exit 0
  fi

  CHANGED_FILES=("${scoped_changed_files[@]}")
  local total_files="${#CHANGED_FILES[@]}"
  local batch_count=$(((total_files + STRIX_PR_SCOPE_MAX_FILES_PER_BATCH - 1) / STRIX_PR_SCOPE_MAX_FILES_PER_BATCH))
  local batch_start=0
  while [ "$batch_start" -lt "$total_files" ]; do
    PULL_REQUEST_SCOPE_FILE_BATCHES+=("$(printf '%s\n' "${CHANGED_FILES[@]:batch_start:STRIX_PR_SCOPE_MAX_FILES_PER_BATCH}")")
    batch_start=$((batch_start + STRIX_PR_SCOPE_MAX_FILES_PER_BATCH))
  done
  printf "Scoped pull request Strix scan to %s changed file(s)" "$total_files" >&2
  if [ "$batch_count" -gt 1 ]; then
    printf " across %s batch(es)" "$batch_count" >&2
  fi
  printf ".\n" >&2
  return 0
}

should_rebalance_pull_request_batch() {
  if ! is_pull_request_event; then
    return 1
  fi
  if [ "$CURRENT_PULL_REQUEST_BATCH_FILE_COUNT" -le 1 ]; then
    return 1
  fi
  if [ "$INFRA_ERROR_DETECTED" -ne 1 ]; then
    return 1
  fi
  if [ "$(remaining_total_budget)" -le 0 ]; then
    return 1
  fi
  if is_timeout_error; then
    return 0
  fi
  return 1
}

extract_vulnerability_locations() {
  local vuln_file="$1"
  local location

  extract_candidate_source_paths_from_report() {
    python3 - "$1" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
patterns = [
    re.compile(r'(?P<path>/workspace/[^\s`]+|[A-Za-z0-9_./-]+\.[A-Za-z0-9_]+):\d+'),
    re.compile(r'^[ \t]*(?:\*\*)?Target:(?:\*\*)?[ \t]*File:[ \t]*(?P<path>/workspace/[^\s`]+|[A-Za-z0-9_./-]+\.[A-Za-z0-9_]+)', re.MULTILINE),
]
seen = set()
for pattern in patterns:
    for match in pattern.finditer(text):
        value = match.group('path').strip()
        if value and value not in seen:
            seen.add(value)
for value in sorted(seen):
    print(value)
PY
  }

  changed_file_is_in_pull_request_scope() {
    local candidate="$1"
    local changed_file
    for changed_file in "${CHANGED_FILES[@]}"; do
      if [ "$candidate" = "$changed_file" ]; then
        return 0
      fi
    done
    return 1
  }

  normalize_vulnerability_location() {
    local raw_location="$1"
    raw_location="$({
      python3 - "$REPO_ROOT" "$REPO_NAME" "$raw_location" <<'PY'
from pathlib import Path
from urllib.parse import unquote
import sys

repo_root = Path(sys.argv[1]).resolve(strict=True)
repo_name = sys.argv[2]
raw_location = unquote(sys.argv[3].strip())
if not raw_location:
    raise SystemExit(1)

prefixes = (
    str(repo_root) + "/",
    f"/workspace/{repo_name}/",
)
for prefix in prefixes:
    if raw_location.startswith(prefix):
        raw_location = raw_location[len(prefix):]
        break

raw_location = raw_location.lstrip("./")
if not raw_location:
    raise SystemExit(1)

candidate = (repo_root / raw_location).resolve(strict=True)
relative = candidate.relative_to(repo_root)
print(relative.as_posix())
PY
    })" || return 1
    if [ -z "$raw_location" ]; then
      return 1
    fi
    if ! is_supported_source_file "$raw_location"; then
      return 1
    fi

    if [ -f "$REPO_ROOT/$raw_location" ] && [ ! -L "$REPO_ROOT/$raw_location" ]; then
      if is_pull_request_event && ! changed_file_is_in_pull_request_scope "$raw_location"; then
        return 1
      fi
      printf '%s\n' "$raw_location"
      return 0
    fi

    return 1
  }

  {
    while IFS= read -r location; do
      normalize_vulnerability_location "$location" || true
    done < <(extract_candidate_source_paths_from_report "$vuln_file")
  } | sort -u
}

evaluate_pull_request_findings() {
  PR_FINDINGS_DECISION="not_applicable"
  if ! is_pull_request_event; then
    return 1
  fi
  if ! load_pull_request_changed_files; then
    PR_FINDINGS_DECISION="block_unmapped"
    echo "Unable to map Strix findings to changed files; failing closed for pull request." >&2
    return 1
  fi

  local threshold_rank
  threshold_rank="$(severity_rank "$STRIX_FAIL_ON_MIN_SEVERITY")"
  local found_threshold_finding=0
  local run_dir vulnerabilities_dir vuln_file line severity rank
  for run_dir in "$STRIX_REPORTS_DIR"/*; do
    if [ ! -d "$run_dir" ] || [ -L "$run_dir" ]; then
      continue
    fi
    if is_preexisting_report_dir "$run_dir"; then
      continue
    fi
    vulnerabilities_dir="$run_dir/vulnerabilities"
    if [ ! -d "$vulnerabilities_dir" ] || [ -L "$vulnerabilities_dir" ]; then
      continue
    fi
    for vuln_file in "$vulnerabilities_dir"/*.md; do
      if [ ! -f "$vuln_file" ] || [ -L "$vuln_file" ]; then
        continue
      fi
      rank=-1
      while IFS= read -r line; do
        if [[ "${line^^}" =~ SEVERITY[[:space:]]*:[[:space:][:punct:]]*(CRITICAL|HIGH|MEDIUM|LOW|INFO|INFORMATIONAL|NONE)([[:space:][:punct:]]|$) ]]; then
          severity="${BASH_REMATCH[1]}"
          rank="$(severity_rank "$severity")"
          if [ "$rank" -gt -1 ]; then
            break
          fi
        fi
      done < <(grep -Ei 'severity[[:space:]]*:' "$vuln_file" || true)
      if [ "$rank" -lt 0 ]; then
        PR_FINDINGS_DECISION="block_unmapped"
        echo "Unrecognized Strix severity marker; failing closed for pull request." >&2
        return 1
      fi
      if [ "$rank" -lt "$threshold_rank" ]; then
        continue
      fi
      found_threshold_finding=1
      mapfile -t vulnerability_locations < <(extract_vulnerability_locations "$vuln_file")
      if [ "${#vulnerability_locations[@]}" -eq 0 ]; then
        PR_FINDINGS_DECISION="block_unmapped"
        echo "Unable to map Strix findings to changed files; failing closed for pull request." >&2
        return 1
      fi
      local changed_file vulnerability_location
      for vulnerability_location in "${vulnerability_locations[@]}"; do
        for changed_file in "${CHANGED_FILES[@]}"; do
          if [ "$vulnerability_location" = "$changed_file" ]; then
            PR_FINDINGS_DECISION="block_changed"
            echo "Strix finding intersects files changed in this pull request." >&2
            return 1
          fi
        done
      done
    done
  done

  if [ "$found_threshold_finding" -eq 1 ]; then
    PR_FINDINGS_DECISION="allow_baseline"
    echo "Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." >&2
    return 0
  fi

  return 1
}

is_vertex_model() {
  case "$1" in
    vertex_ai/* | vertex_ai_beta/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolved_llm_api_base_for_model() {
  local model="$1"

  if is_vertex_model "$model"; then
    return 0
  fi

  local llm_api_base_value="${RAW_LLM_API_BASE:-$ORIGINAL_LLM_API_BASE}"
  llm_api_base_value="${llm_api_base_value%%/generateContent*}"
  llm_api_base_value="${llm_api_base_value%%:generateContent*}"
  llm_api_base_value="$(trim_whitespace "$llm_api_base_value")"
  if [ -z "$llm_api_base_value" ]; then
    return 0
  fi
  if [[ "$llm_api_base_value" =~ [[:space:][:cntrl:]] ]]; then
    echo "ERROR: LLM_API_BASE must not contain whitespace or control characters." >&2
    return 2
  fi
  if [[ ! "$llm_api_base_value" =~ ^https://[^[:space:]]+$ ]]; then
    echo "ERROR: LLM_API_BASE must be an https URL when configured." >&2
    return 2
  fi
  printf '%s\n' "$llm_api_base_value"
}

## Run a single strix invocation against TARGET_PATH with the given model.
## Builds a child-only environment so secrets and model routing do not leak
## through the parent shell process.
## Returns 0 on success (strix exit 0), 1 on any failure.
## The caller is responsible for retry/fallback logic; process-level timeout
## wrapping prevents CI from hanging indefinitely.
run_strix_once() {
  local model="$1"
  local rc
  local llm_api_base_value
  local resolved_target_path
  local timeout_seconds="$STRIX_PROCESS_TIMEOUT_SECONDS"
  if [ "$STRIX_TOTAL_TIMEOUT_SECONDS" -gt 0 ]; then
    local remaining_budget
    remaining_budget="$(remaining_total_budget)"
    if [ "$remaining_budget" -le 0 ]; then
      printf "Strix quick scan exceeded total timeout of %ss.\n" "$STRIX_TOTAL_TIMEOUT_SECONDS" | tee "$STRIX_LOG" >&2
      return 1
    fi
    if [ "$timeout_seconds" -eq 0 ] || [ "$remaining_budget" -lt "$timeout_seconds" ]; then
      timeout_seconds="$remaining_budget"
    fi
  fi
  if ! llm_api_base_value="$(resolved_llm_api_base_for_model "$model")"; then
    return 1
  fi
  if ! resolved_target_path="$(resolve_scan_target_path "$TARGET_PATH")"; then
    return 1
  fi
  local start_epoch
  start_epoch="$(date +%s)"
  set -o pipefail
  set +e
  STRIX_CHILD_MODEL="$model" \
    STRIX_CHILD_LLM_API_KEY="$LLM_API_KEY" \
    STRIX_CHILD_LLM_API_BASE="$llm_api_base_value" \
    STRIX_CHILD_REPORTS_DIR="$ACTIVE_REPORTS_DIR" \
    python3 - "$timeout_seconds" "$resolved_target_path" "$SCAN_MODE" "$STRIX_LOG" <<'PY'
import os
import pathlib
import signal
import subprocess
import sys

timeout_seconds = int(sys.argv[1])
target_path = sys.argv[2]
scan_mode = sys.argv[3]
log_path = pathlib.Path(sys.argv[4])
process_timeout = None if timeout_seconds == 0 else timeout_seconds
child_env = os.environ.copy()
child_env["STRIX_LLM"] = os.environ["STRIX_CHILD_MODEL"]
child_env["LLM_MODEL"] = os.environ["STRIX_CHILD_MODEL"]
child_env["LLM_API_KEY"] = os.environ["STRIX_CHILD_LLM_API_KEY"]
child_env["STRIX_REPORTS_DIR"] = os.environ["STRIX_CHILD_REPORTS_DIR"]
llm_api_base = os.environ.get("STRIX_CHILD_LLM_API_BASE", "")
if llm_api_base:
    child_env["LLM_API_BASE"] = llm_api_base
else:
    child_env.pop("LLM_API_BASE", None)

command = ["strix", "-n", "-t", target_path, "--scan-mode", scan_mode]

try:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=child_env,
        start_new_session=True,
    )
    output, _ = process.communicate(timeout=process_timeout)
    if output:
        sys.stdout.write(output)
    log_path.write_text(output or "", encoding="utf-8")
    raise SystemExit(process.returncode)
except subprocess.TimeoutExpired:
    os.killpg(process.pid, signal.SIGTERM)
    try:
        output, _ = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
    if output:
        sys.stdout.write(output)
    log_path.write_text(output or "", encoding="utf-8")
    raise SystemExit(124)
PY
  rc=$?
  set -e
  local end_epoch
  end_epoch="$(date +%s)"
  local elapsed=$((end_epoch - start_epoch))

  if [ "$rc" -eq 124 ]; then
    echo "Strix run timed out after ${timeout_seconds}s." | tee -a "$STRIX_LOG" >&2
  fi

  if [ "$rc" -eq 0 ]; then
    printf "Strix run succeeded for model '%s' in %ds.\n" "$model" "$elapsed" >&2
    return 0
  fi

  printf "Strix run failed for model '%s' after %ds (exit code %d).\n" "$model" "$elapsed" "$rc" >&2

  # Sticky flag: record that at least one attempt hit an infrastructure
  # error.  STRIX_LOG is overwritten per-attempt, so without this flag the
  # below-threshold guard in has_only_below_threshold_vulnerabilities()
  # would only see the *last* attempt's log — missing infrastructure errors
  # from earlier attempts whose partial reports may still sit in the reports
  # directory.
  if has_detected_infrastructure_error; then
    INFRA_ERROR_DETECTED=1
  fi

  return 1
}

## Determines whether the last strix failure is a transient error eligible
## for same-model retry (up to STRIX_TRANSIENT_RETRY_PER_MODEL times).
## Two error families qualify:
##   - RateLimit / RESOURCE_EXHAUSTED / HTTP 429
##   - MidStreamFallbackError (litellm mid-stream provider switch)
## Timeouts remain infrastructure errors for guard logic, but the caller should
## move directly to fallback model evaluation instead of spending the remaining
## budget retrying the same slow model.
is_transient_same_model_retry_error() {
  return 1
}

run_strix_with_transient_retry() {
  local model="$1"
  local max_attempts=$((STRIX_TRANSIENT_RETRY_PER_MODEL + 1))
  local attempt=1

  while [ "$attempt" -le "$max_attempts" ]; do
    if run_strix_once "$model"; then
      return 0
    fi

    if [ "$attempt" -ge "$max_attempts" ]; then
      return 1
    fi

    if [ "$STRIX_TOTAL_TIMEOUT_SECONDS" -gt 0 ] && [ "$(remaining_total_budget)" -le 0 ]; then
      printf "Strix quick scan exceeded total timeout of %ss.\n" "$STRIX_TOTAL_TIMEOUT_SECONDS" | tee "$STRIX_LOG" >&2
      return 1
    fi

    if ! is_transient_same_model_retry_error; then
      return 1
    fi

    local retry_reason="transient error"
    if is_rate_limit_error; then
      retry_reason="rate limit"
    elif is_midstream_fallback_error; then
      retry_reason="midstream fallback"
    fi
    echo "Retrying model '$model' due to $retry_reason (attempt $((attempt + 1))/$max_attempts)." >&2
    sleep "$STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS"
    attempt=$((attempt + 1))
  done

  return 1
}

is_vertex_not_found_error() {
  # Match Vertex/LiteLLM model-not-found errors.
  # These functions are only called within the Vertex fallback path
  # (gated by is_vertex_model), so the risk of matching target-app
  # 404s is low — strix separates LLM errors from scan findings.
  if grep -Fq 'litellm.NotFoundError: Vertex_aiException' "$STRIX_LOG"; then
    return 0
  fi

  if grep -Fq 'litellm.NotFoundError' "$STRIX_LOG" && grep -Eq '"status"[[:space:]]*:[[:space:]]*"NOT_FOUND"' "$STRIX_LOG"; then
    return 0
  fi

  # Compact Vertex/GCP API error format — require a provider marker
  # (litellm, VertexAI, or Vertex) nearby so we don't misclassify
  # target-application 404 JSON responses as LLM provider errors.
  if grep -Eq '"status"[[:space:]]*:[[:space:]]*"NOT_FOUND"' "$STRIX_LOG" &&
    grep -Eiq '(litellm|VertexAI|Vertex_ai|vertex\.ai|google\.cloud)' "$STRIX_LOG"; then
    return 0
  fi

  if grep -Eq 'Publisher Model .*was not found' "$STRIX_LOG"; then
    return 0
  fi

  return 1
}

is_rate_limit_error() {
  if grep -Fq 'RateLimitError' "$STRIX_LOG"; then
    return 0
  fi

  if grep -Eq '"status"[[:space:]]*:[[:space:]]*"RESOURCE_EXHAUSTED"' "$STRIX_LOG"; then
    return 0
  fi

  # Bare HTTP 429 — require a provider marker so we don't misclassify
  # target-application rate-limit responses as LLM provider errors.
  if grep -Eq '(^|[^0-9])429([^0-9]|$)' "$STRIX_LOG" &&
    grep -Eiq '(litellm|RateLimitError|VertexAI|Vertex_ai|vertex\.ai|openai|anthropic)' "$STRIX_LOG"; then
    return 0
  fi

  return 1
}

## Timeout classification — three-tier hierarchy:
##
##   1. litellm.exceptions.Timeout — SDK-level timeout raised by litellm.
##      Always trusted as a genuine LLM timeout; no provider marker required.
##
##   2. httpx.ReadTimeout / httpcore.ReadTimeout — transport-layer timeouts
##      from litellm/openai SDK internals. These strings can also appear in
##      target-application logs, so an LLM-provider marker (LLM_PROVIDER_ONLY_REGEX)
##      must be present nearby to classify as an LLM timeout.
##
##   3. Bare "Connection timed out" — generic OS/network timeout string.
##      Requires LLM_PROVIDER_ONLY_REGEX to avoid misclassifying target-app
##      or infrastructure network timeouts as LLM errors.
##
## All three tiers feed into infrastructure-error detection and trigger
## fallback model evaluation before the total budget is exhausted.  Same-model
## retries remain reserved for rate-limit and mid-stream fallback errors.
is_timeout_error() {
  # Tier 1: litellm SDK timeout — provider-specific, always trusted.
  if grep -Fq 'litellm.exceptions.Timeout' "$STRIX_LOG"; then
    return 0
  fi

  if grep -Fq 'Strix run timed out after' "$STRIX_LOG"; then
    return 0
  fi

  # Tier 2a: httpx transport timeout — requires LLM provider marker.
  # httpx/httpcore are litellm/openai SDK transport libraries, but their
  # timeout strings could appear in target-application logs too.
  # Require an LLM provider-context marker (LLM_PROVIDER_ONLY_REGEX) to
  # avoid misclassification — the httpx/httpcore/requests transport names
  # in the timeout string itself are not sufficient proof of an LLM call.
  if grep -Fq 'httpx.ReadTimeout' "$STRIX_LOG" &&
    grep -Eiq "$LLM_PROVIDER_ONLY_REGEX" "$STRIX_LOG"; then
    return 0
  fi

  # Tier 2b: httpcore transport timeout — requires LLM provider marker.
  if grep -Fq 'httpcore.ReadTimeout' "$STRIX_LOG" &&
    grep -Eiq "$LLM_PROVIDER_ONLY_REGEX" "$STRIX_LOG"; then
    return 0
  fi

  # Tier 3: Bare "Connection timed out" — require a real LLM provider-context
  # marker.  httpx/httpcore/requests are transport libraries that could
  # appear in any network timeout context, so they are NOT valid markers
  # here.  Use LLM_PROVIDER_ONLY_REGEX (defined alongside
  # PROVIDER_CONTEXT_REGEX) to prevent drift.
  if grep -Fq 'Connection timed out' "$STRIX_LOG" &&
    grep -Eiq "$LLM_PROVIDER_ONLY_REGEX" "$STRIX_LOG"; then
    return 0
  fi

  return 1
}

is_midstream_fallback_error() {
  if grep -Fq 'MidStreamFallbackError' "$STRIX_LOG"; then
    return 0
  fi

  return 1
}

# Narrower variant: LLM providers only, excluding HTTP transport libraries
# (httpx, httpcore, requests). Used for generic transport failures where
# library names alone are insufficient to prove the timeout/connection error
# originated from an LLM provider rather than the target application.
LLM_PROVIDER_ONLY_REGEX='(litellm|openai|anthropic|VertexAI|Vertex_ai|vertex\.ai|google\.cloud)'

# Detect whether the strix log contains evidence of infrastructure-level
# errors (timeout, rate-limit, transport failures) that indicate the scan
# was interrupted or incomplete.  Used as a guard to prevent the
# below-threshold override from silently passing an aborted scan.
has_detected_infrastructure_error() {
  if is_timeout_error; then
    return 0
  fi

  if is_rate_limit_error; then
    return 0
  fi

  if is_midstream_fallback_error; then
    return 0
  fi

  # Generic strix non-zero exit with known transport/connection errors
  # that don't fall into the specific categories above.
  # Use LLM_PROVIDER_ONLY_REGEX (not PROVIDER_CONTEXT_REGEX) to avoid
  # false positives: PROVIDER_CONTEXT_REGEX includes httpx/httpcore/requests
  # which would self-match on e.g. "requests.exceptions.ConnectionError"
  # from target-application logs.
  if grep -Eiq '(ConnectionError|ConnectionRefusedError|ConnectionResetError|SSLError|ProxyError|NetworkError)' "$STRIX_LOG" &&
    grep -Eiq "$LLM_PROVIDER_ONLY_REGEX" "$STRIX_LOG"; then
    return 0
  fi

  return 1
}

latest_strix_report_dir() {
  local latest=""
  local run_dir

  for run_dir in "$STRIX_REPORTS_DIR"/*; do
    if [ ! -d "$run_dir" ] || [ -L "$run_dir" ]; then
      continue
    fi

    if is_preexisting_report_dir "$run_dir"; then
      continue
    fi

    if [ -z "$latest" ] || [ "$run_dir" -nt "$latest" ]; then
      latest="$run_dir"
    fi
  done

  if [ -z "$latest" ]; then
    return 1
  fi

  echo "$latest"
}

has_only_below_threshold_vulnerabilities() {
  local threshold_rank
  threshold_rank="$(severity_rank "$STRIX_FAIL_ON_MIN_SEVERITY")"

  local found_any_report=0
  local found_any_vuln_file=0
  local global_max_rank=-1
  local saw_any_severity=0

  local run_dir
  for run_dir in "$STRIX_REPORTS_DIR"/*; do
    if [ ! -d "$run_dir" ] || [ -L "$run_dir" ]; then
      continue
    fi

    if is_preexisting_report_dir "$run_dir"; then
      continue
    fi

    local vulnerabilities_dir="$run_dir/vulnerabilities"
    if [ ! -d "$vulnerabilities_dir" ] || [ -L "$vulnerabilities_dir" ]; then
      continue
    fi

    found_any_report=1
    local vuln_file
    local line
    local severity
    local rank

    for vuln_file in "$vulnerabilities_dir"/*.md; do
      if [ ! -f "$vuln_file" ] || [ -L "$vuln_file" ]; then
        continue
      fi

      found_any_vuln_file=1

      while IFS= read -r line; do
        if [[ "${line^^}" =~ SEVERITY[[:space:]]*:[[:space:][:punct:]]*(CRITICAL|HIGH|MEDIUM|LOW|INFO|INFORMATIONAL|NONE)([[:space:][:punct:]]|$) ]]; then
          severity="${BASH_REMATCH[1]}"
        else
          continue
        fi

        rank="$(severity_rank "$severity")"
        if [ "$rank" -lt 0 ]; then
          continue
        fi

        saw_any_severity=1
        if [ "$rank" -gt "$global_max_rank" ]; then
          global_max_rank="$rank"
        fi
      done < <(grep -Ei 'severity[[:space:]]*:' "$vuln_file" || true)
    done
  done

  if [ "$found_any_report" -eq 0 ]; then
    return 1
  fi

  # Guard against incomplete/aborted scans: if reports exist but no
  # vulnerability files were found, the scan likely aborted before
  # completing its analysis — refuse the bypass.
  if [ "$found_any_vuln_file" -eq 0 ]; then
    echo "Reports exist but contain no vulnerability files; scan may be incomplete." >&2
    return 1
  fi

  if [ "$saw_any_severity" -eq 0 ]; then
    return 1
  fi

  # Guard against incomplete scans due to infrastructure errors.
  # Use the sticky INFRA_ERROR_DETECTED flag instead of re-reading
  # STRIX_LOG, because STRIX_LOG is overwritten per-attempt.  If an
  # earlier attempt hit an infrastructure error (timeout, rate-limit,
  # transport failure) and produced a partial report that now sits in
  # the reports directory, the *current* STRIX_LOG may show a different
  # failure — or even success — but the partial report's low-severity
  # findings must not be treated as a clean scan result.
  if [ "$INFRA_ERROR_DETECTED" -eq 1 ]; then
    echo "Below-threshold findings detected, but infrastructure errors occurred during this pipeline run; refusing bypass due to potentially incomplete scan." >&2
    return 1
  fi

  if [ "$global_max_rank" -lt "$threshold_rank" ]; then
    echo "Strix findings are below configured fail threshold '$STRIX_FAIL_ON_MIN_SEVERITY'; allowing pipeline continuation." >&2
    return 0
  fi

  return 1
}

is_hallucinated_endpoint_finding() {
  # Configurable list of source directories to check for endpoints.
  # Defaults to "." (i.e. TARGET_PATH itself) so that both
  # STRIX_TARGET_PATH=./ and STRIX_TARGET_PATH=./src work correctly
  # without producing bogus double-nested paths like ./src/src.
  # Set STRIX_SOURCE_DIRS (space-separated) to override.
  local source_dirs_raw="${STRIX_SOURCE_DIRS:-.}"
  local resolved_dirs=()
  local dir_entry

  # Disable globbing so that entries like "*" or "[" in STRIX_SOURCE_DIRS
  # are not expanded by pathname expansion during word-splitting.
  set -f
  for dir_entry in $source_dirs_raw; do
    local candidate="${TARGET_PATH%/}/$dir_entry"
    if [ -d "$candidate" ] && [ ! -L "$candidate" ]; then
      resolved_dirs+=("$candidate")
    fi
  done
  set +f

  if [ "${#resolved_dirs[@]}" -eq 0 ]; then
    return 1
  fi

  local latest_report_dir
  if ! latest_report_dir="$(latest_strix_report_dir)"; then
    return 1
  fi

  local endpoint_seen=0
  local endpoint_present_in_source=0
  local endpoint
  local vuln_file

  for vuln_file in "$latest_report_dir"/vulnerabilities/*.md; do
    if [ ! -f "$vuln_file" ] || [ -L "$vuln_file" ]; then
      continue
    fi

    while IFS= read -r endpoint; do
      if [ -z "$endpoint" ]; then
        continue
      fi

      endpoint_seen=1
      local search_dir
      for search_dir in "${resolved_dirs[@]}"; do
        # Exclude the strix reports directory and common non-source
        # directories from the source search to prevent accidental
        # matches and reduce runtime (especially when STRIX_TARGET_PATH=./).
        #
        # Each exclude-dir:
        #   STRIX_REPORTS_DIR — strix output itself (would always match).
        #       Both the full path and basename are excluded so that
        #       nested paths like "reports/strix_runs" are also caught.
        #   .git             — VCS internals
        #   node_modules     — JS/TS dependencies (may contain API strings)
        #   vendor           — Go/PHP vendored deps
        #   __pycache__      — Python bytecode cache
        #   .venv            — Python virtualenv
        #   target           — Rust/Java build artifacts
        #   .mypy_cache      — mypy type-check cache
        #   .pytest_cache    — pytest result cache
        #   dist             — common build output directory
        #   build            — common build output directory
        #   .tox             — Python tox test environments
        #   .ruff_cache      — Ruff linter cache
        if grep -r -Fq \
          --exclude-dir="$STRIX_REPORTS_DIR" \
          --exclude-dir="$(basename "$STRIX_REPORTS_DIR")" \
          --exclude-dir=".git" \
          --exclude-dir="node_modules" \
          --exclude-dir="vendor" \
          --exclude-dir="__pycache__" \
          --exclude-dir=".venv" \
          --exclude-dir="target" \
          --exclude-dir=".mypy_cache" \
          --exclude-dir=".pytest_cache" \
          --exclude-dir="dist" \
          --exclude-dir="build" \
          --exclude-dir=".tox" \
          --exclude-dir=".ruff_cache" \
          -- "$endpoint" "$search_dir"; then
          endpoint_present_in_source=1
          break
        fi
      done
      if [ "$endpoint_present_in_source" -eq 1 ]; then
        break
      fi
    done < <(grep -Eo '/api/[[:alnum:]_./-]+' "$vuln_file" | sort -u)

    if [ "$endpoint_present_in_source" -eq 1 ]; then
      break
    fi
  done

  if [ "$endpoint_seen" -eq 0 ]; then
    return 1
  fi

  if [ "$endpoint_present_in_source" -eq 1 ]; then
    return 1
  fi

  echo "Detected Strix report endpoint(s) absent from source; treating as retryable model inconsistency." >&2
  return 0
}

is_vertex_retryable_error() {
  if is_vertex_not_found_error; then
    return 0
  fi

  if is_rate_limit_error; then
    return 0
  fi

  if is_timeout_error; then
    return 0
  fi

  if is_midstream_fallback_error; then
    return 0
  fi

  if is_hallucinated_endpoint_finding; then
    return 0
  fi

  return 1
}

run_current_target_scan() {
  INFRA_ERROR_DETECTED=0

  if run_strix_with_transient_retry "$PRIMARY_MODEL"; then
    return 0
  fi

  if should_rebalance_pull_request_batch; then
    return 75
  fi

  if has_only_below_threshold_vulnerabilities; then
    return 0
  fi

  if evaluate_pull_request_findings; then
    return 0
  fi

  case "$PR_FINDINGS_DECISION" in
    block_changed | block_unmapped)
      return 1
      ;;
  esac

  if ! is_vertex_model "$PRIMARY_MODEL"; then
    echo "Strix quick scan failed with a non-recoverable error." >&2
    return 1
  fi

  if ! is_vertex_retryable_error; then
    echo "Strix quick scan failed with a non-recoverable error." >&2
    return 1
  fi

  if [ -z "${STRIX_VERTEX_FALLBACK_MODELS+x}" ]; then
    FALLBACK_MODELS_RAW="vertex_ai/gemini-2.5-pro vertex_ai/gemini-2.5-flash"
  else
    FALLBACK_MODELS_RAW="$STRIX_VERTEX_FALLBACK_MODELS"
  fi
  FALLBACK_MODELS_RAW="${FALLBACK_MODELS_RAW//$'\r'/ }"
  FALLBACK_MODELS_RAW="${FALLBACK_MODELS_RAW//$'\n'/ }"
  read -r -a FALLBACK_MODELS <<<"$FALLBACK_MODELS_RAW"

  fallback_tried=0
  for candidate_raw in "${FALLBACK_MODELS[@]}"; do
    candidate="$(normalize_model "$candidate_raw")"
    if [ -z "$candidate" ] || [ "$candidate" = "$PRIMARY_MODEL" ]; then
      if [ -n "$candidate" ]; then
        echo "Skipping fallback model '$candidate' — same as primary model." >&2
      fi
      continue
    fi

    fallback_tried=1
    echo "Primary Vertex model unavailable; retrying with fallback '$candidate'."
    if run_strix_with_transient_retry "$candidate"; then
      echo "Strix quick scan succeeded with fallback model '$candidate'."
      return 0
    fi

    if has_only_below_threshold_vulnerabilities; then
      return 0
    fi

    if ! is_vertex_retryable_error; then
      echo "Strix quick scan failed with a non-recoverable error." >&2
      return 1
    fi
  done

  if [ "$fallback_tried" -eq 0 ]; then
    if [ "${#FALLBACK_MODELS[@]}" -eq 0 ]; then
      echo "ERROR: No fallback models configured (STRIX_VERTEX_FALLBACK_MODELS is empty). Configure distinct models." >&2
    else
      echo "ERROR: All configured fallback models are the same as the primary model '$PRIMARY_MODEL'. Configure distinct models in STRIX_VERTEX_FALLBACK_MODELS." >&2
    fi
  fi

  echo "Configured Vertex model and fallback models were unavailable." >&2
  return 1
}

prepare_pull_request_scan_scope

run_pull_request_batch_files() {
  local batch_label="$1"
  local total_batches="$2"
  local batch_files_text="$3"
  local -a batch_files=()
  mapfile -t batch_files <<<"$batch_files_text"
  if [ "${#batch_files[@]}" -eq 0 ]; then
    echo "ERROR: pull request Strix batch '$batch_label' has no files to scan." >&2
    return 1
  fi

  local previous_batch_file_count="$CURRENT_PULL_REQUEST_BATCH_FILE_COUNT"
  CURRENT_PULL_REQUEST_BATCH_FILE_COUNT="${#batch_files[@]}"
  build_pull_request_scope_dir "${batch_files[@]}"
  TARGET_PATH="$LAST_PULL_REQUEST_SCOPE_DIR"
  echo "Running pull request Strix batch ${batch_label}/${total_batches}." >&2

  run_current_target_scan
  local batch_rc=$?
  if [ "$batch_rc" -eq 0 ]; then
    capture_preexisting_report_dirs
    CURRENT_PULL_REQUEST_BATCH_FILE_COUNT="$previous_batch_file_count"
    return 0
  fi

  if [ "$batch_rc" -eq 75 ]; then
    local midpoint=$((CURRENT_PULL_REQUEST_BATCH_FILE_COUNT / 2))
    if [ "$midpoint" -le 0 ]; then
      midpoint=1
    fi
    echo "Rebalancing pull request Strix batch ${batch_label}/${total_batches} into smaller batches after timeout." >&2
    local first_half second_half
    first_half="$(printf '%s\n' "${batch_files[@]:0:midpoint}")"
    second_half="$(printf '%s\n' "${batch_files[@]:midpoint}")"
    if ! run_pull_request_batch_files "${batch_label}.1" "$total_batches" "$first_half"; then
      CURRENT_PULL_REQUEST_BATCH_FILE_COUNT="$previous_batch_file_count"
      return 1
    fi
    if ! run_pull_request_batch_files "${batch_label}.2" "$total_batches" "$second_half"; then
      CURRENT_PULL_REQUEST_BATCH_FILE_COUNT="$previous_batch_file_count"
      return 1
    fi
    CURRENT_PULL_REQUEST_BATCH_FILE_COUNT="$previous_batch_file_count"
    return 0
  fi

  CURRENT_PULL_REQUEST_BATCH_FILE_COUNT="$previous_batch_file_count"
  return 1
}

if [ "${#PULL_REQUEST_SCOPE_FILE_BATCHES[@]}" -gt 0 ]; then
  total_batches="${#PULL_REQUEST_SCOPE_FILE_BATCHES[@]}"
  batch_number=0
  for batch_files_text in "${PULL_REQUEST_SCOPE_FILE_BATCHES[@]}"; do
    batch_number=$((batch_number + 1))
    if ! run_pull_request_batch_files "$batch_number" "$total_batches" "$batch_files_text"; then
      exit 1
    fi
  done
  exit 0
fi

if run_current_target_scan; then
  exit 0
fi

exit 1
