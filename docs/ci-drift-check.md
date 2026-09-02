# CI schema-drift gate

Status date: 2026-08-09
Lifecycle: authenticated Bearer comparison fix `active_pr`; snapshot
creation and deployment-gate orchestration `downstream`
Owner: repository maintainers for the script; deployment pipeline owner for use

Gate deploys on "the database schema matches the approved baseline". This is
the highest-leverage automation the snapshot/diff APIs enable: schema changes
stop sneaking into production unreviewed.

## How it works

1. **Baseline**: after a reviewed migration lands, take a snapshot and record
   its UUID as the approved baseline (e.g. in your pipeline variables).
2. **Check**: before this script runs, the pipeline must create and wait for a
   fresh successful snapshot of the target database, then diff it against the baseline:
   `GET /api/snapshots/{target}/diff?against={baseline}`.
3. **Gate**: `diff.summary.has_changes == false` → deploy proceeds. Otherwise
   the pipeline fails and prints the structured summary. It deliberately does
   not print reconciliation SQL, schema comments, or full identifiers into CI
   logs.

The diff is name-keyed (never `relation_oid`), so re-introspecting the same
database yields a stable, empty diff — no false drift between runs.

## Ready-made script

[`scripts/ci/check_schema_drift.sh`](../scripts/ci/check_schema_drift.sh):

```bash
PG_ERD_BASE_URL=https://erd.example.com \
PG_ERD_TOKEN="pgerd_..." \
./scripts/ci/check_schema_drift.sh "$BASELINE_SNAPSHOT_UUID" "$TARGET_SNAPSHOT_UUID"
```

Exit codes: `0` no drift · `1` drift detected (summary on stderr) · `2`
snapshot missing/unauthorized.

### GitHub Actions example

```yaml
- name: Schema drift gate
  env:
    PG_ERD_BASE_URL: ${{ vars.PG_ERD_BASE_URL }}
    PG_ERD_TOKEN: ${{ secrets.PG_ERD_API_KEY }}
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

The script accepts an OIDC access token or a `pgerd_` API key through the
`Authorization: Bearer` header. It does not support session-cookie auth, and it
does not create or poll the target snapshot itself.
