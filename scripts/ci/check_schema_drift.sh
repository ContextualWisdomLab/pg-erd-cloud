#!/usr/bin/env bash
# Gate a deploy on "no unexpected schema drift".
#
# Compares the latest schema snapshot (target) against an approved baseline
# snapshot (base) via the diff API and fails the pipeline when the schema
# changed. Pair with GET .../migration.sql to print the SQL that would
# reconcile the drift.
#
# Usage:
#   PG_ERD_BASE_URL=https://erd.example.com \
#   PG_ERD_COOKIE="session=..." \
#   ./check_schema_drift.sh <baseline_snapshot_uuid> <target_snapshot_uuid>
#
# Exit codes:
#   0  no drift (schemas identical)
#   1  drift detected (diff summary printed, migration SQL printed)
#   2  usage / API error (snapshot missing or unauthorized)
set -euo pipefail

usage() {
  echo "usage: check_schema_drift.sh <baseline_uuid> <target_uuid>" >&2
  echo "required env: PG_ERD_BASE_URL and PG_ERD_COOKIE" >&2
}

if [ "$#" -ne 2 ]; then
  echo "drift-check: expected exactly 2 snapshot UUID arguments; got $#." >&2
  usage
  exit 2
fi

if [ -z "${PG_ERD_BASE_URL:-}" ]; then
  echo "drift-check: PG_ERD_BASE_URL is not set." >&2
  usage
  exit 2
fi

if [ -z "${PG_ERD_COOKIE:-}" ]; then
  echo "drift-check: PG_ERD_COOKIE is not set." >&2
  usage
  exit 2
fi

BASE_UUID="$1"
TARGET_UUID="$2"

api() {
  local path="$1"
  if ! curl --fail --silent --show-error \
    --cookie "${PG_ERD_COOKIE}" \
    "${PG_ERD_BASE_URL}${path}"
  then
    echo "drift-check: API request failed for ${path}." >&2
    return 1
  fi
}

if ! DIFF_JSON="$(api "/api/snapshots/${TARGET_UUID}/diff?against=${BASE_UUID}")"; then
  echo "drift-check: unable to fetch schema diff for target=${TARGET_UUID} against baseline=${BASE_UUID}." >&2
  exit 2
fi

if ! STATUS="$(printf '%s' "${DIFF_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))')"; then
  echo "drift-check: diff API response was not valid JSON." >&2
  exit 2
fi
if [ "${STATUS}" != "ok" ]; then
  echo "drift-check: snapshot not found or unauthorized (status=${STATUS})" >&2
  exit 2
fi

if ! HAS_CHANGES="$(printf '%s' "${DIFF_JSON}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d["diff"]["summary"]["has_changes"]).lower())')"; then
  echo "drift-check: diff API response is missing diff.summary.has_changes." >&2
  exit 2
fi

if [ "${HAS_CHANGES}" = "false" ]; then
  echo "drift-check: OK - schema matches the approved baseline."
  exit 0
fi

echo "drift-check: DRIFT DETECTED - schema differs from the approved baseline." >&2
printf '%s' "${DIFF_JSON}" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["diff"]["summary"], indent=2))' >&2
echo "--- migration SQL that would reconcile the drift ---" >&2
api "/api/snapshots/${TARGET_UUID}/migration.sql?against=${BASE_UUID}" >&2 || true
exit 1
