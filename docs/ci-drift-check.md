# CI schema-drift gate

Gate deploys on "the database schema matches the approved baseline". This is
the highest-leverage automation the snapshot/diff APIs enable: schema changes
stop sneaking into production unreviewed.

## How it works

1. **Baseline**: after a reviewed migration lands, take a snapshot and record
   its UUID as the approved baseline (e.g. in your pipeline variables).
2. **Check**: on every deploy, take a fresh snapshot of the target database and
   diff it against the baseline:
   `GET /api/snapshots/{target}/diff?against={baseline}`.
3. **Gate**: `diff.summary.has_changes == false` → deploy proceeds. Otherwise
   the pipeline fails and prints both the structured summary and the exact
   migration SQL that would reconcile the drift
   (`GET /api/snapshots/{target}/migration.sql?against={baseline}`).

The diff is name-keyed (never `relation_oid`), so re-introspecting the same
database yields a stable, empty diff — no false drift between runs.

## Ready-made script

[`scripts/ci/check_schema_drift.sh`](../scripts/ci/check_schema_drift.sh):

```bash
PG_ERD_BASE_URL=https://erd.example.com \
PG_ERD_COOKIE="session=..." \
./scripts/ci/check_schema_drift.sh "$BASELINE_SNAPSHOT_UUID" "$TARGET_SNAPSHOT_UUID"
```

Exit codes: `0` no drift · `1` drift detected (summary + migration SQL on
stderr) · `2` snapshot missing/unauthorized.

### GitHub Actions example

```yaml
- name: Schema drift gate
  env:
    PG_ERD_BASE_URL: ${{ vars.PG_ERD_BASE_URL }}
    PG_ERD_COOKIE: ${{ secrets.PG_ERD_SESSION_COOKIE }}
  run: |
    ./scripts/ci/check_schema_drift.sh \
      "${{ vars.SCHEMA_BASELINE_UUID }}" \
      "${{ steps.snapshot.outputs.snapshot_uuid }}"
```

## Reviewing drift before promoting a baseline

When drift is intentional (a planned migration), review it with:

- `GET /diff?against=` — structured change list
- `GET /migration-safety?against=` — each change classified
  safe / warning / destructive
- `GET /migration.sql?against=` — the reconciling SQL

then promote the new snapshot UUID as the baseline.
