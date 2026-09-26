# Product–Technical Gap Baseline

Status: Proposed
Evidence date: 2026-09-27
Product PR: [#1222](https://github.com/ContextualWisdomLab/pg-erd-cloud/pull/1222)
Source exact product head before baseline restoration: `18e386c46a1463bd700cdfc8c26d4dc10ca1d7df`
Current fail-closed boundary evidence: `7d9ee21230b817c12147250c8745fd9461b1f71d`

## PRD

Goal: keep ERD interaction and export responsive without changing deterministic handle identifiers, Unicode behavior, or graph semantics.

Scenes: an editor pans, zooms, resizes, reconnects, exports, and reloads a large ERD. Cache eviction, lifecycle changes, stale state, or Unicode input must not change identifiers or retain unbounded memory. Offline, permission, read-only, stale, conflict, retry, and busy states require a structured table/list alternative.

## TRD

The proposed implementation places a bounded LRU inside `sanitizeHandleId`. It is not accepted performance architecture. Compare it with no cache and simpler caller-level/native memoization on the real React Flow render and export paths.

Record hardware/runtime, dataset shape, warm-up, sample size, failure denominator, cache hit/miss/eviction rate, retained heap, median, p95, and lifecycle cleanup. Functional tests alone do not establish a performance gain.

## Context Map

- **ERD Editor:** owns interaction, deterministic handle IDs, import/export, persistence, recovery.
- **React Flow:** external rendering boundary behind the product adapter.
- **Browser Runtime:** heap, GC, main-thread, layout, paint, pointer/touch/keyboard.
- **Translation Authority:** supplies ko/en/ja/zh/vi/es/de/fr screen strings; ontology labels remain separate.

## UML

```mermaid
sequenceDiagram
  participant View as ERD View
  participant ID as Handle ID
  participant Cache as Proposed LRU
  View->>ID: sanitize(label)
  ID->>Cache: lookup
  alt hit
    Cache-->>ID: deterministic ID
  else miss
    ID->>ID: encode Unicode
    ID->>Cache: bounded insert
  end
  ID-->>View: exact ID
```

## ERD

No persistent entity is added. Cache entries are ephemeral `source_text -> sanitized_handle_id` pairs, never domain truth or export data, and must be discardable without changing persisted ERDs.

## Exact-head acceptance matrix

| Dimension | Current evidence | Merge acceptance | Status |
|---|---|---|---|
| Determinism | Focused tests exist | Same exact ID with cache off/on and after reload/export | FAIL |
| Unicode/collision | Empty string remains `c-empty`; missing values now throw; Unicode and emoji exact values covered | Add combining, RTL, long, and full collision fixtures | PARTIAL |
| Semantics | Public input remains `string`; `null`/`undefined` fail closed instead of collapsing into `c-empty` | Cache state never becomes domain truth | SOURCE PASS |
| Accessibility | None current | WCAG 2.2 AA; pointer/touch/keyboard; reduced motion; AT | FAIL |
| Responsive | None current | 320/768/desktop and intermediate widths | FAIL |
| Locales | None current | ko/en/ja/zh/vi/es/de/fr wrapping/font fallback | FAIL |
| Performance | Unmeasured | Real render/export median+p95, heap/GC, hit/miss/eviction | FAIL |
| Large data | None current | Representative small/median/large ERDs | FAIL |
| Import/export | None current | Exact IDs and graph equivalence after round trip | FAIL |
| Recovery | None current | reload/crash/rollback/stale/conflict/retry cleanup | FAIL |
| Dependency | Unrelated 1,660-line lockfile delta removed at `18e386c4…` | Keep product manifest/lock ownership aligned | PASS |
| Hosted validation | Not GREEN | exact-head CI/security/SBOM/provenance and approval | FAIL |

## Gap and action

| Gap | Action | Owner | Status |
|---|---|---|---|
| Unsupported performance claim | Reproducible real-path benchmark | pg-erd-cloud | Proposed |
| Hand-rolled LRU complexity | Compare no-cache/caller/native alternatives | pg-erd-cloud | Proposed |
| Lifecycle risk | Retained-heap and cleanup contract | pg-erd-cloud | Proposed |
| Missing-name collision | Keep the domain type `string`; reject runtime `null`/`undefined` while preserving explicit empty-string behavior | pg-erd-cloud | Resolved at `7d9ee212…`; hosted checks pending |
| Lockfile expansion | Removed without reverting product/cache tests | dependency owner | Resolved |
| Missing UX evidence | Browser/AT/responsive/8-locale matrix | pg-erd-cloud | Proposed |

## Decision

Keep #1222 Draft. Preserve valid source and tests while rejecting unmeasured performance claims. Accept only after this exact-head matrix is GREEN; otherwise retain a feature boundary or remove the cache with an ordinary-forward commit.
