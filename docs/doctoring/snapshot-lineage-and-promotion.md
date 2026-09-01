# Snapshot lineage, promotion, retention & recovery

Status: **in progress** — first increment (pure model + algorithms) landed.
Tracks issue
[#948](https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/948)
("[Product Gap] Add snapshot promotion, bitemporal lineage, retention, and
recovery workflows").

## Why

pg-erd-cloud creates immutable snapshots and computes diffs, but a timestamped
list is not a lifecycle. Buyers cannot answer, with product-owned evidence:
which snapshot was the approved baseline for a release/environment; who
promoted / superseded / rejected it and why; what views, exports, migration
plans, and connector artifacts were derived from it; what is retained,
archived, legally held, or deletable; and how to recover a known-good
diagram/model **without pretending metadata rollback rolls back a live
customer database**.

## Decision — pure model + algorithms (this increment)

`app/lineage/` — **no database, no I/O**. Persistence (Alembic tables,
repositories, an HTTP surface, PROV-JSON-LD projection) is a later increment.

### Time model — capture time ≠ valid time

`SnapshotLineage` keeps these as separate facts:

| field | meaning |
| --- | --- |
| `captured_at` | when target metadata was observed |
| `available_at` | when the completed snapshot became usable |
| `valid_from` / `valid_to` | when a promoted baseline is declared applicable |
| `recorded_at` / `superseded_at` | when pg-erd-cloud learned or changed the declaration |
| `knowledge_cutoff` | latest evidence allowed in an audit/export |

A later-captured snapshot may describe an earlier database state, so capture
time is never silently treated as valid time.

### Typed derivations, not one generic edge

`build_lineage_graph(snapshot_ids, derivations)` builds a DAG with edges kept
**by kind**: `captured_from`, `imported_from`, `normalized_from`,
`compared_with`, `exported_from`, `planned_from`. It rejects an unknown kind, a
self-loop, and a cycle (`LineageCycleError` names the involved ids); it reports
`orphans` and `dangling_references` rather than failing, and returns a
topological order, `roots`, and `leaves`.

### Promotion — append-only, optimistic concurrency

`apply_promotion(current_promotions, request)` returns a **new** history:
changing the approved baseline **closes the prior row's `valid_to`** (and sets
`superseded_at`) and appends a new row with `valid_to = None` and an
incremented `version`. It never rewrites a row. A stale `expected_version`
raises `PromotionConflictError`, so two concurrent promoters cannot both win.
Environment codes are `development` / `staging` / `production` — not tied to
any customer's naming.

### Retention — a decision record, never a delete

`decide_retention(policy, snapshot, *, now, under_legal_hold, is_promoted)`
returns one of `retain` / `archive_eligible` / `delete_eligible` /
`legal_hold`. It performs **no deletion** — the disposition is evidence a
human or a separate, audited job acts on. A promoted baseline is never
`delete_eligible` unless the policy sets `applies_to_promoted`. Legal hold
always wins.

### Recovery restores metadata + a diagram state only

`RecoveryCheckpoint` restores product metadata and a selected saved diagram
state. **Live customer-database recovery requires a separately approved
migration/backup workflow and is never implied by this feature.**

## Deferred (later increments on #948)

- Normalized tables + Alembic migration (`snapshot_lineage`,
  `snapshot_derivation`, `snapshot_promotion`, `promotion_environment`,
  `retention_policy`, `retention_disposition`, `legal_hold_record`,
  `recovery_checkpoint`, `recovery_action`, `audit_event_record`).
- Repositories + a `Settings`-gated HTTP surface for history / compare /
  promote / supersede / archive / recover with accessible non-color-only
  state cues.
- Optional PROV-JSON-LD / JSON-LD projection with the relational model
  authoritative.
- Embedding the exact snapshot / promotion / tool / commit / policy
  references into every export and migration plan for reproducibility.

## References (APA 7th)

Snodgrass, R. T. (2000). *Developing time-oriented database applications in
SQL*. Morgan Kaufmann.

Jensen, C. S., & Snodgrass, R. T. (2009). Bitemporal data. In L. Liu & M. T.
Özsu (Eds.), *Encyclopedia of database systems* (pp. 285–287). Springer.
https://doi.org/10.1007/978-0-387-39940-9_663

World Wide Web Consortium. (2013). *PROV-DM: The PROV data model* (W3C
Recommendation). https://www.w3.org/TR/prov-dm/
