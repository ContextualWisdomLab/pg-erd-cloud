# Normalization & functional-dependency assessment

Status: **in progress** — first increment under review. Tracks issue
[#947](https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/947)
("[Product Gap] Add evidence-backed 3NF, functional-dependency, and
hot-partition assessment").

## Buyer-visible problem

pg-erd-cloud can introspect objects, lint naming, and flag wide tables, but it
cannot yet give an architect a defensible answer to:

1. Which relations have catalog-visible normalization risks or review
   preconditions?
2. Which findings are observed, declared, inferred, or intentionally excepted?
3. What additional evidence is required before a normal-form claim is made?

The product also stores immutable schema and queue payloads as `JSONB`. That
may be a justified evidence envelope, but JSON storage must never be described
as proof of a normal form.

## Decision

Add a **catalog-evidence** normalization assessment as a pure
`app.spec` analyzer (`app/spec/normalization_assessment.py`,
`assess_normalization(snapshot, *, waivers=None)`), matching the existing
`relationship_inference` / `constraint_inventory` / `wide_tables` analyzers:
no I/O and stable output over the common snapshot contract.

Provider-specific catalog representations are normalized at the introspection
adapter boundary. In particular, MySQL/MariaDB `STATISTICS` unique indexes are
published as common `UNIQUE` constraint records before the domain analyzer sees
them. Snowflake's literal `ARRAY` type is recognized as an array representation.
This keeps provider DTO details out of the schema-assessment logic.

**Evidence, not certification.** The analyzer uses only declared primary keys,
`UNIQUE` constraints, `NOT NULL` flags, column types, and declared foreign
keys. It never profiles table data and never infers a functional dependency
from a column name. Absence of a catalog-visible warning does **not** establish
BCNF, 3NF, or 2NF because an undeclared functional dependency remains possible.
A relation with no active finding therefore receives `catalog_reviewed` with
`evidence_class = "inferred"`, not `bcnf`.

Every finding carries an explicit `evidence_class`:

| class | meaning |
| --- | --- |
| `observed` | directly visible in the catalog (for example an array column) |
| `declared` | follows from a declared database constraint |
| `inferred` | a structural review precondition is present; the catalog cannot establish the dependency itself |
| `proposed` | reserved for a later increment that emits a concrete remediation |
| `waived` | an explicitly scoped caller waiver matched the finding; the finding remains visible |

**No side effects.** The analyzer emits no DDL and never auto-normalizes.

### Findings in this increment

| kind | scope | evidence | what the catalog supports |
| --- | --- | --- | --- |
| `non_atomic_column` | 1NF | `observed` | array column (high confidence) or `json`/`jsonb` column (medium; caveated as a possible deliberate envelope) |
| `missing_candidate_key` | BCNF review | `inferred` | no catalog-visible PK or total `NOT NULL UNIQUE` candidate key; domain-key evidence may still be missing |
| `nullable_unique_determinant` | BCNF review | `declared` | a nullable `UNIQUE` is not treated as a total candidate key; null semantics must be checked for the source dialect |
| `partial_dependency_precondition` | 2NF review | `inferred` | at least one minimal candidate key is composite and non-prime columns exist; this is a precondition, not proof of a partial dependency |

Candidate keys are minimal declared keys. A declared unique superkey that
strictly contains another declared key is excluded before prime/non-prime
attributes are derived. A composite candidate key is reviewed independently of
whether a separate single-column candidate key also exists.

Each relation gets one conservative label:
`catalog_reviewed`, `bcnf_review`, `2nf_review`, `1nf_review`, or
`insufficient_evidence`. Waived findings do not drive the label.

Finding identifiers use stable schema/relation names, finding kind, and source
object names rather than transient relation OIDs so recreating an unchanged
table does not silently break finding correlation.

### Waivers

`scope.schema`, `scope.relation`, and `scope.kind` are individually optional,
but a scope must contain at least one of those supported keys. Empty scopes and
unknown or misspelled scope keys never match. This is fail-closed: a typo must
not waive findings globally.

A valid executable example is:

```python
waivers = [
    {
        "scope": {
            "schema": "public",
            "relation": "schema_snapshot_data",
            "kind": "non_atomic_column",
        },
        "owner": "data-platform",
        "reason": "immutable evidence envelope",
        "review_date": "2026-09-01",
        "expiry": "2027-03-01",
    }
]
result = assess_normalization(snapshot, waivers=waivers)
```

A matched finding is returned with `evidence_class = "waived"` and the waiver
metadata attached. Signed, persisted waiver records with an approval workflow
remain a later increment.

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

## Hot-partition & growth assessment — landed (first increment)

`app.spec.hot_partition_assessment.assess_hot_partitions(snapshot, *,
capacity_profile=None)` and `GET
/api/snapshots/{schema_snapshot_uuid}/hot-partition-assessment`
(`HotPartitionAssessmentOut`, same access model as the sibling analyzers).

Catalog evidence (declared keys, column types/defaults, PostgreSQL
partitioning metadata) plus an **optional explicit capacity profile** only —
no live workload assumed, no data sampled, no DDL. Findings:
`append_heavy_table` (1NF-style naming + monotonic/time signal),
`unbounded_retention` (append-heavy with no `deleted_at`/`expires_at`/…),
`monotonic_key_hot_page` (single-column serial/identity PK),
`partition_semantics_review` (a partitioned table whose PRIMARY KEY / UNIQUE
omits the partition key — global uniqueness not enforced), `skew_candidate`
(a growing table with a low-cardinality `status`/`tenant`/`project`/… axis).
Concrete remediations are emitted as `proposed` only when a
`capacity_profile` supplies the missing quantities
(`expected_rows` / `retention_days` / `write_concentration_keys`) or the
signal is catalog-declared.

Deferred: generated `EXPLAIN` / `EXPLAIN ANALYZE` partition-pruning fixtures
against a real PostgreSQL, and persisted `capacity_profile` records.

## Exact-value HTML view — landed

`app.spec.assessment_html.render_assessment_html(report, *, title)` renders
either report envelope (they share the `summary` + `relation_assessments` +
`findings` shape) as a self-contained accessible HTML fragment: every cell is
`html.escape(…, quote=True)`, state is a text label (`[declared]`,
`risk: review`) never colour alone, one `<table>` per finding kind with
`<caption>` and `<th scope>`, scoped inline `<style>`, no external
CSS/JS/scripts. Both assessment endpoints accept `?format=html` (returns
`text/html`); the uniform JSON not-found response is unchanged regardless of
`format`.

## Transitive-dependency (3NF) assessment — landed

`app.spec.transitive_dependency_assessment.assess_transitive_dependencies(
snapshot, *, declared_functional_dependencies=None, waivers=None)` adds the
third-normal-form layer the catalog-only analyzer deliberately skips. It
works from two evidence sources and never infers a dependency from column
names:

- **Catalog only** → `non_key_reference_cluster` (evidence class
  `inferred`, confidence `low`): a relation carries more than one
  foreign-key column that is not a candidate key, alongside non-prime
  descriptive columns. That is the *structural precondition* for a
  transitive dependency, not proof of one — the finding says so and points
  the caller at profiling or a declared FD.
- **Caller-declared functional dependencies** → `transitive_dependency_via_declared_fd`
  (evidence class `declared`): a supplied FD `X → Y` where `X` is not a
  superkey and every column of `Y` is non-prime. That is a genuine 3NF
  violation, asserted only because the caller supplied the dependency.
  Each such finding is paired with a `candidate_3nf_split` proposal
  (evidence class `proposed`, never applied automatically).

`declared_functional_dependencies` is an optional list of
`{"relation": "schema.table", "determinant": [...], "dependent": [...]}`.
Entries naming an unknown relation or column are returned under
`unresolved_declared_fds` with a reason rather than silently dropped.
Waivers use the same `scope` shape as `assess_normalization`. Row-level FD
discovery from table data stays out of scope (it needs profiling, which
belongs in a separate service).

## Signed waiver records — landed

`app.spec.waiver_record` makes a waiver **tamper-evident** so an auditor can
trust one without re-reviewing it. It is a pure function pair with no
database, network, or filesystem access.

- `sign_waiver(waiver, *, signer, signed_at, key_id, key)` returns
  `{"waiver": <deep copy>, "signature": {"algo", "signer", "signed_at",
  "key_id", "value"}}`. `value` is an HMAC-SHA256 (`algo` is the constant
  `WAIVER_SIGNATURE_ALGO = "hmac-sha256"`) over the canonical JSON of the
  waiver **with the signature metadata folded in** as `_meta`, so altering
  the signer or the timestamp invalidates the signature exactly as altering
  the waiver body does. The caller's dict is deep-copied, never mutated.
- `verify_waiver_signature(record, *, key)` recomputes that HMAC from
  `record["waiver"]` and the `signer` / `signed_at` / `key_id` in
  `record["signature"]` and compares it with `hmac.compare_digest`
  (constant time). Any edit to the body or the metadata, or a wrong key,
  returns `False`; a missing signature or a non-`hmac-sha256` `algo` raises
  `ValueError`.
- Canonical form sorts keys at every level, so a waiver rebuilt in a
  different key order still verifies. The secret `key` is supplied by the
  caller and is never stored, logged, or echoed into the record.

What remains deferred: **persisting** these signed records (with owner,
review date, scope, expiry) alongside the assessment run, and key
rotation / `key_id` resolution — that is storage-layer work tracked with
the persisted-assessment-run item below.

## Deferred (later bounded increments on #947)

- **Row-level functional-dependency discovery** — profiling a sample of
  table data to *find* the dependencies a caller would otherwise have to
  declare; belongs in a separate profiling service, not this pure analyzer.
- **Persisted assessment runs** — an accessible
  non-color-only HTML rendering, and the `assessment_run` /
  `capacity_profile` / `partition_candidate` / `remediation_action` records
  persisted with tool/commit provenance.
- **Persisted signed waiver records** — the signing / verification core has
  landed (`app.spec.waiver_record`, above); storing the signed records with
  owner, review date, scope, and expiry is the remaining storage-layer step.
- **Typed public snapshot/report contracts** — replace broad `dict[str, Any]`
  surfaces with explicit common-snapshot and assessment contracts after the
  cross-dialect record shape is settled, rather than introducing a second
  competing schema contract in this repair.

## Rust boundary decision — DEFERRED

Per the Rust decision gate on issue #951, a Rust boundary is justified only
when the path is a measured production CPU/security hotspot, the algorithm and
data contract are stable, a language reference implementation with golden
fixtures exists, and a bounded FFI/WASM/service interface avoids per-row
crossing.

This increment is bounded set arithmetic over *declared* keys and constraints;
it does not enumerate arbitrary attribute subsets or discover functional
dependencies from data. There is therefore no measured reason to introduce the
repository's first Rust toolchain for this path yet. Dependency/UCC discovery
becomes a separate algorithmic concern when profiling is added and must be
benchmarked before a language-boundary decision.

An ADR for a Rust core will be written only if that later measured path meets
the repository's Rust decision gate.

## References (APA 7th)

Codd, E. F. (1970). A relational model of data for large shared data banks.
*Communications of the ACM, 13*(6), 377–387.
https://doi.org/10.1145/362384.362685

Relevance: establishes the relational model, keys, and normalization as
semantic constraints rather than properties that can be inferred from storage
layout alone.

Codd, E. F. (1971). Normalized data base structure: A brief tutorial. In
*Proceedings of the 1971 ACM SIGFIDET Workshop on Data Description, Access and
Control* (pp. 1–17). Association for Computing Machinery.
https://doi.org/10.1145/1734714.1734716

Relevance: primary exposition of normalization and removal of repeating groups;
it supports treating nested/repeating catalog representations as review
signals without turning that signal into an automatic decomposition theorem.

Date, C. J. (2019). *Database design and relational theory: Normal forms and
all that jazz* (2nd ed.). Apress.
https://doi.org/10.1007/978-1-4842-5540-7

Relevance: modern treatment of candidate keys and normal forms; it supports the
minimal-superkey requirement used before prime and non-prime attributes are
derived.

Lucchesi, C. L., & Osborn, S. L. (1978). Candidate keys for relations.
*Journal of Computer and System Sciences, 17*(2), 270–279.
https://doi.org/10.1016/0022-0000(78)90009-0

Relevance: studies candidate-key computation from functional dependencies and
reinforces the distinction between minimal candidate keys and non-minimal
superkeys. The current catalog-only analyzer does not attempt general FD-based
key discovery.

National Institute of Standards and Technology. (2008). *The keyed-hash
message authentication code (HMAC)* (FIPS PUB 198-1).
https://doi.org/10.6028/NIST.FIPS.198-1

Rundgren, A., Jordan, B., & Erdtman, S. (2020). *JSON Canonicalization Scheme
(JCS)* (RFC 8785). RFC Editor. https://doi.org/10.17487/RFC8785
