# Normalization & functional-dependency assessment

Status: **in progress** — first increment landed. Tracks issue
[#947](https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/947)
("[Product Gap] Add evidence-backed 3NF, functional-dependency, and
hot-partition assessment").

## Buyer-visible problem

pg-erd-cloud can introspect objects, lint naming, and flag wide tables, but it
cannot give an architect a defensible answer to:

1. Which relations appear to violate normalization or mix independent facts?
2. Which findings are certain, inferred, or intentionally excepted?
3. What is the customer's next action for each finding?

The product also stores immutable schema and queue payloads as `JSONB`. That
may be a justified evidence envelope, but JSON storage must never be described
as third-normal-form proof.

## Decision

Add a **catalog-evidence** normalization assessment as a pure
`app.spec` analyzer (`app/spec/normalization_assessment.py`,
`assess_normalization(snapshot, *, waivers=None)`), matching the existing
`relationship_inference` / `constraint_inventory` / `wide_tables` analyzers:
no I/O, dialect-agnostic over the common snapshot JSON shape, stable output.

**Evidence, not theorems.** The analyzer uses only declared primary keys,
`UNIQUE` constraints, `NOT NULL` flags, column types, and declared foreign
keys. It never profiles table data and never infers a functional dependency
from column *names*. Every finding carries an explicit `evidence_class`:

| class | meaning |
| --- | --- |
| `observed` | directly visible in the catalog (e.g. an array column) |
| `declared` | proven from a declared constraint (e.g. a `UNIQUE` on a nullable column is not a total key) |
| `inferred` | a structural precondition is present; the catalog cannot confirm an actual dependency |
| `proposed` | reserved for a future increment that emits a concrete remediation |
| `waived` | a caller-supplied waiver matched this finding; it is recorded, not hidden |

**No side effects.** The analyzer emits no DDL and never auto-normalizes.

### Findings in this increment

| kind | scope | evidence | what the catalog proves |
| --- | --- | --- | --- |
| `non_atomic_column` | 1NF | `observed` | array column (high confidence) or `json`/`jsonb` column (medium; caveated as a possible deliberate envelope) |
| `missing_candidate_key` | BCNF | `inferred` | no PK and no `NOT NULL UNIQUE` ⇒ normal form cannot be assessed |
| `nullable_unique_determinant` | BCNF | `declared` | a `UNIQUE` covering a nullable column is not a total key in PostgreSQL |
| `partial_dependency_precondition` | 2NF | `inferred` | the only candidate key is composite and non-key columns exist — the *precondition* for a 2NF partial dependency, not a violation |

Each relation also gets a coarse `normal_form` label
(`bcnf` / `bcnf_review` / `2nf_review` / `1nf_review` /
`insufficient_evidence`) with the evidence class of that label. `waived`
findings do not drive the label.

### Waivers

`assess_normalization` accepts `waivers=[{ "scope": {"schema"?, "relation"?,
"kind"?}, "owner", "reason", "review_date", "expiry" }]`. A finding whose
relation and kind match every field the scope sets is returned with
`evidence_class = "waived"` and an attached `waiver` object. An empty scope
never matches (it is never a deliberate waiver). Signed, persisted waiver
records with an approval workflow are a later increment.

## Report envelope & HTTP surface — landed

`app.spec.normalization_report.build_normalization_report(snapshot, *,
waivers=None)` wraps the analyzer output additively with `report_version`,
`generated_at`, a stable `schema_fingerprint` (SHA-256 of the canonical
snapshot JSON), and a `summary` block (counts by normal form and evidence
class plus a one-line buyer-facing `headline`).

`GET /api/snapshots/{schema_snapshot_uuid}/normalization-assessment`
(`NormalizationAssessmentOut`) returns that envelope as JSON. It follows the
same access model as the sibling snapshot analyzers (`/wide-tables`,
`/constraint-inventory`, `/naming-lint`): authenticated, read-only, IDOR-safe
via `_get_authorized_snapshot` (a missing or unauthorized snapshot returns a
uniform `not_found`). No feature flag — the assessment is a shipped product
feature, not a hidden experiment; no DDL, no writes.

## Deferred (later bounded increments on #947)

- **3NF / transitive-dependency** detection — needs data profiling or
  declared functional dependencies; catalog evidence alone cannot prove a
  transitive dependency without asserting a theorem from names.
- **Hot-partition & growth assessment** — write/read concentration by
  tenant/status/time key, queue/audit/share-link tables, `EXPLAIN` pruning
  fixtures against a real PostgreSQL.
- **Exact-value HTML table + persisted assessment runs** — an accessible
  non-color-only HTML rendering, and the `assessment_run` /
  `capacity_profile` / `partition_candidate` / `remediation_action` records
  persisted with tool/commit provenance.
- **Persisted, signed waiver records** with owner, review date, scope, expiry.

## Rust boundary decision — DEFERRED

Per the Rust decision gate on issue #951, a Rust boundary is justified only
when the path is a **measured** production CPU/security hotspot, the algorithm
and data contract are stable, a language reference implementation with golden
fixtures exists, and a bounded FFI/WASM/service interface avoids per-row
crossing.

This increment establishes the reference implementation and golden fixtures.
The analysis itself is bounded set arithmetic over a single relation's
*declared* constraints (candidate keys are enumerated from the PK and
`NOT NULL UNIQUE` constraints, not searched over all attribute subsets), so it
is `O(relations × constraints)` and not currently a hotspot. General candidate-
key discovery and functional-dependency closure — which the deferred 3NF and
profiling work will need — are the genuine combinatorial cost (candidate-key
discovery is NP-hard in the number of attributes) and are the correct place to
revisit a Rust core once the performance profile from #951 exists. Until then,
adding the repository's first Rust toolchain, `maturin` build backend, and
hash-locked cargo lockfiles would be unmeasured risk.

An ADR for the Rust core will be written alongside that work, with parity
fixtures against this Python reference.

## References (APA 7th)

Codd, E. F. (1972). Further normalization of the data base relational model.
In R. Rustin (Ed.), *Data base systems* (pp. 33-64). Prentice-Hall.

Date, C. J. (2019). *Database design and relational theory: Normal forms and
all that jazz* (2nd ed.). Apress.
https://doi.org/10.1007/978-1-4842-5540-7

Lucchesi, C. L., & Osborn, S. L. (1978). Candidate keys for relations.
*Journal of Computer and System Sciences, 17*(2), 270-279.
https://doi.org/10.1016/0022-0000(78)90009-0
