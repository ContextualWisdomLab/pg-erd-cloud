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

## Deferred (later bounded increments on #947)

- **3NF / transitive-dependency** detection — requires declared functional
  dependencies or profiled evidence; catalog keys and column names alone cannot
  establish the relevant dependencies.
- **Hot-partition & growth assessment** — write/read concentration by
  tenant/status/time key, queue/audit/share-link tables, and real-database
  pruning evidence.
- **Report envelope & HTTP surface** — the versioned `assessment_run` /
  `finding_record` / `evidence_record` / `waiver_record` /
  `capacity_profile` / `partition_candidate` / `remediation_action` model, a
  gated read-only `/api` endpoint, and JSON + exact-value HTML + buyer-facing
  summary renderings.
- **Persisted, signed waiver records** with owner, review date, scope, expiry.
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
