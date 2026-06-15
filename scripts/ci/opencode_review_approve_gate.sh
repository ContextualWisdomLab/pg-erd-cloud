#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 4 ] && [ $# -ne 5 ]; then
  echo "usage: $0 <expected_head_sha> <expected_run_id> <expected_run_attempt> <comment_body_file> [normalized_json_file]" >&2
  exit 64
fi

EXPECTED_HEAD_SHA="$1"
EXPECTED_RUN_ID="$2"
EXPECTED_RUN_ATTEMPT="$3"
COMMENT_FILE="$4"
NORMALIZED_JSON_FILE="${5:-}"

if [ ! -r "$COMMENT_FILE" ]; then
  echo "error: cannot read comment body file: $COMMENT_FILE" >&2
  exit 65
fi

SENTINEL_LINE="$(
  grep -E '<!--[[:space:]]+opencode-review-gate[[:space:]]+head_sha=[^[:space:]]+[[:space:]]+run_id=[^[:space:]]+[[:space:]]+run_attempt=[^[:space:]]+[[:space:]]+-->' \
    "$COMMENT_FILE" | head -1 || true
)"

if [ -z "$SENTINEL_LINE" ]; then
  echo "MISSING_SENTINEL"
  exit 2
fi

SENTINEL_HEAD_SHA="$(echo "$SENTINEL_LINE" | sed -nE 's/.*head_sha=([^[:space:]]+).*/\1/p')"
SENTINEL_RUN_ID="$(echo "$SENTINEL_LINE" | sed -nE 's/.*run_id=([^[:space:]]+).*/\1/p')"
SENTINEL_RUN_ATTEMPT="$(echo "$SENTINEL_LINE" | sed -nE 's/.*run_attempt=([^[:space:]]+).*/\1/p')"

if [ "$SENTINEL_HEAD_SHA" != "$EXPECTED_HEAD_SHA" ]; then
  echo "SHA_MISMATCH"
  exit 3
fi

if [ -z "$SENTINEL_RUN_ID" ] || [ -z "$SENTINEL_RUN_ATTEMPT" ]; then
  echo "MISSING_SENTINEL"
  exit 2
fi

if [ "$EXPECTED_RUN_ID" != "-" ] && [ "$SENTINEL_RUN_ID" != "$EXPECTED_RUN_ID" ]; then
  echo "MISSING_SENTINEL"
  exit 2
fi

if [ "$EXPECTED_RUN_ATTEMPT" != "-" ] && [ "$SENTINEL_RUN_ATTEMPT" != "$EXPECTED_RUN_ATTEMPT" ]; then
  echo "MISSING_SENTINEL"
  exit 2
fi

CONTROL_JSON="$(
  awk '
    /^<!--[[:space:]]*opencode-review-control-v1[[:space:]]*$/ { in_block=1; next }
    in_block && /^-->[[:space:]]*$/ { exit }
    in_block { print }
  ' "$COMMENT_FILE"
)"

if [ -z "$CONTROL_JSON" ]; then
  echo "NO_CONCLUSION"
  exit 4
fi

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT
printf '%s\n' "$CONTROL_JSON" >"$TMP_JSON"

if ! jq -e . "$TMP_JSON" >/dev/null 2>&1; then
  echo "NO_CONCLUSION"
  exit 4
fi

CONTROL_HEAD_SHA="$(jq -r '.head_sha // empty' "$TMP_JSON")"
CONTROL_RUN_ID="$(jq -r '.run_id // empty' "$TMP_JSON")"
CONTROL_RUN_ATTEMPT="$(jq -r '.run_attempt // empty' "$TMP_JSON")"
RESULT="$(jq -r '.result // empty' "$TMP_JSON")"

if [ "$CONTROL_HEAD_SHA" != "$EXPECTED_HEAD_SHA" ]; then
  echo "SHA_MISMATCH"
  exit 3
fi

if [ "$EXPECTED_RUN_ID" != "-" ] && [ "$CONTROL_RUN_ID" != "$EXPECTED_RUN_ID" ]; then
  echo "MISSING_SENTINEL"
  exit 2
fi

if [ "$EXPECTED_RUN_ATTEMPT" != "-" ] && [ "$CONTROL_RUN_ATTEMPT" != "$EXPECTED_RUN_ATTEMPT" ]; then
  echo "MISSING_SENTINEL"
  exit 2
fi

if ! jq -e '
  type == "object"
  and (.head_sha | type == "string" and length > 0)
  and (.run_id | type == "string" and length > 0)
  and (.run_attempt | type == "string" and length > 0)
  and (.result == "APPROVE" or .result == "REQUEST_CHANGES")
  and (.reason | type == "string" and length > 0)
  and (.summary | type == "string" and length > 0)
  and (.findings | type == "array")
  and (
    if .result == "REQUEST_CHANGES" then (.findings | length > 0)
    else (.findings | length == 0)
    end
  )
  and all(.findings[];
    (.path | type == "string" and length > 0)
    and (.line | type == "number" and . > 0 and floor == .)
    and (.severity | type == "string" and length > 0)
    and (.title | type == "string" and length > 0)
    and (.problem | type == "string" and length > 0)
    and (.root_cause | type == "string" and length > 0)
    and (.fix_direction | type == "string" and length > 0)
    and (.regression_test_direction | type == "string" and length > 0)
    and (.suggested_diff | type == "string" and length > 0)
  )
' "$TMP_JSON" >/dev/null; then
  echo "NO_CONCLUSION"
  exit 4
fi

if [ -n "$NORMALIZED_JSON_FILE" ]; then
  jq -c '{head_sha, run_id, run_attempt, result, reason, summary, findings}' "$TMP_JSON" >"$NORMALIZED_JSON_FILE"
fi

echo "$RESULT"
exit 0
