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

BASE_UUID="${1:?usage: check_schema_drift.sh <baseline_uuid> <target_uuid>}"
TARGET_UUID="${2:?usage: check_schema_drift.sh <baseline_uuid> <target_uuid>}"
: "${PG_ERD_BASE_URL:?set PG_ERD_BASE_URL}"
: "${PG_ERD_COOKIE:?set PG_ERD_COOKIE (authenticated session cookie)}"

api() {
  curl --fail --silent --show-error \
    --cookie "${PG_ERD_COOKIE}" \
    "${PG_ERD_BASE_URL}$1"
}

DIFF_JSON="$(api "/api/snapshots/${TARGET_UUID}/diff?against=${BASE_UUID}")"

STATUS="$(printf '%s' "${DIFF_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))')"
if [ "${STATUS}" != "ok" ]; then
  echo "drift-check: snapshot not found or unauthorized (status=${STATUS})" >&2
  exit 2
fi

HAS_CHANGES="$(printf '%s' "${DIFF_JSON}" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d["diff"]["summary"]["has_changes"]).lower())')"

if [ "${HAS_CHANGES}" = "false" ]; then
  echo "drift-check: OK — schema matches the approved baseline."
  exit 0
fi

echo "drift-check: DRIFT DETECTED — schema differs from the approved baseline." >&2
printf '%s' "${DIFF_JSON}" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["diff"]["summary"], indent=2))' >&2
echo "--- migration SQL that would reconcile the drift ---" >&2
api "/api/snapshots/${TARGET_UUID}/migration.sql?against=${BASE_UUID}" >&2 || true
exit 1
