# Product and technical gap baseline

- Last evidence review: 2026-08-27
- Product: pg-erd-cloud
- Baseline authority: protected `main`, live GitHub pull-request state, repository ADR/doctoring, and exact-head checks
- Update scope in PR #996: relationship-aware ERD node layout and its commercial-license boundary

This is a living gap baseline, not a replacement for GitHub's live state. A pull request, check, review, or branch can change after this document is committed. Merge and release decisions must always re-read the exact current head.

## Product responsibility

pg-erd-cloud owns physical database schema observation, ERD editing and review, schema snapshots and differences, and database-oriented export evidence. It does not own enterprise architecture, a semantic catalog, or inferred organizational lineage. Those responsibilities remain in their dedicated CWL products and are connected through versioned contracts.

The buyer outcome is:

> Understand an existing database accurately, review intended changes safely, preserve explainable layout and annotation state, and export implementation evidence without losing PostgreSQL identity or exposing restricted metadata.

## Current product slices

| Capability | Current evidence | Gap state | Required next action |
|---|---|---|---|
| Relationship-aware ERD node placement | PR #996 uses exact MIT-licensed Dagre 3.1.0 and Graphlib 4.0.3; initial conversion and toolbar action share a deterministic fail-closed boundary | Implemented on the PR branch; not shipped until merge | Complete final exact-head CI, central review, security, dependency, and independent-approval gates |
| Saved ERD view CRUD contract | Open PR #723 provides backend update and typed frontend API foundations | API foundation is not a complete buyer workspace | Deliver Save, Save As, Open, Rename, Delete, dirty-state, recovery, optimistic concurrency, and permission-aware UI after the contract merges |
| Design-system authority | Open PR #944 owns the Storybook design-token inventory and paired Figma evidence | Separate lane; not duplicated by #996 | Integrate graph/loading/error states through the owning design-system lane |
| PostgreSQL relation identity | Clean replacement PR #990 addresses Unicode, spaces, mixed case, and dotted quoted identifiers in relationship inference | Open; layout must consume exact identifiers without becoming a second identity authority | Merge the identity fix through its own checks and rerun relevant integration tests on combined main |
| Security-sensitive DSN and JWT handling | Open security PRs include #993 and #995 | Independent of layout but release-blocking when applicable | Triage duplicates, validate current heads, and merge through security gates without mixing their changes into #996 |
| Export and physical-schema evidence | Existing DDL, DBML, Prisma, data dictionary, snapshot and diff paths; additional open lanes remain | Broad capability exists, but format fidelity and evidence completeness continue to evolve | Keep each format's identity, quoting, provenance, and failure contracts independently testable |

## Gap closed by PR #996

### Buyer problem

The previous initial layout and `ERD 자동 정렬` action placed tables in an alphabetical fixed grid. Buyers had to reconstruct foreign-key flow manually because referenced/master tables and dependent tables had no structural ordering.

### Implemented contract

- parent/reference tables precede dependent child tables;
- LR and TB directions exist in the pure layout boundary;
- cycles, parallel foreign keys, disconnected tables, missing endpoints, repeated or empty edge identifiers, and Unicode identifiers have regression coverage;
- node and relationship registration use locale-independent code-unit ordering;
- measured sizes are preferred, while pre-measurement geometry conservatively includes table comments, rendered column rows, column comments/examples, overflow rows, and index rows;
- input nodes and product edge semantics are not mutated;
- complete finite geometry is required before publishing any coordinate;
- layout failure preserves every existing coordinate and does not overwrite the previous Undo boundary;
- UI tests assert applied coordinates, exact Undo restoration, and calculation-failure state preservation;
- snapshot initialization and explicit auto-layout use the same code path;
- exact dependency versions, MIT declarations, runtime dependency shape, required notices, and production-bundle notice distribution are checked offline in CI.

### Claim boundary

This closes relationship-aware **node placement**. It does not close:

- port-aware orthogonal relationship routing;
- table-obstacle avoidance;
- globally optimal edge-crossing reduction;
- stable incremental layout with pinned nodes;
- compound schema or domain groups;
- large-schema main-thread latency;
- saved-view conflict resolution;
- visual screenshot and assistive-technology validation.

## Remaining buyer-visible layout gaps

### 1. Column-port and orthogonal routing

Current React Flow `smoothstep` rendering can still produce visually ambiguous paths in dense diagrams. The next routing slice must preserve exact child/parent column handles, avoid table rectangles, bound bend count, and retain route provenance. ELK, yFiles, Graphviz, or a custom router may be evaluated, but no dependency may be adopted without a separate ADR, commercial-use/license review, benchmark, and migration plan.

### 2. Incremental and pinned-node layout

A buyer who manually places key tables expects unrelated changes not to rearrange the entire mental map. The product needs explicit pinned-node semantics, selection-scoped layout, and a movement-cost contract before claiming incremental layout.

### 3. Large-schema execution and virtualization

No published performance envelope currently supports a specific table/FK count. A reproducible benchmark corpus must measure wall-clock time, browser long tasks, heap growth, coordinate validity, render time, and interaction latency. Moving the pure layout boundary to a Web Worker is a candidate only after measurement identifies main-thread layout as a material bottleneck.

### 4. Persisted layout preferences

The pure function supports LR and TB, but the product does not yet expose and persist direction, spacing, scope, pinning, or routing mode per saved view. These settings belong in the versioned saved-view contract, not ad hoc local state.

### 5. Compound grouping

Business groups and database schemas need a defined relationship to layout clusters. A later design must distinguish visual grouping from database ownership and avoid treating a color group as an authoritative schema boundary.

### 6. Visual and accessibility evidence

The new geometry is behavior-tested but does not yet have checked screenshot regression evidence. Product validation must cover dense relationships, zoom/fit, loading, failure, Undo, keyboard operation, reduced motion, exact-value alternatives, print/export, and screen-reader announcements. Reusable states should enter the established Figma/Storybook authority rather than forming a second design system.

## Commercial dependency baseline

| Package | Exact version | Runtime role | License | Distribution obligation recorded |
|---|---:|---|---|---|
| `@dagrejs/dagre` | 3.1.0 | layered node layout | MIT | exact notice in reviewed source, public Vite artifact, and production `dist` artifact |
| `@dagrejs/graphlib` | 4.0.3 | directed multigraph structure | MIT | exact notice in reviewed source, public Vite artifact, and production `dist` artifact |

The CI verifier deliberately fails if the exact versions, MIT declarations, reviewed runtime dependency graph, notice text, public notice copy, or production-build notice changes. This is a bounded assertion for the new layout subtree, not a repository-wide legal certification.

## Verification state for PR #996

| Evidence | State at this document update |
|---|---|
| Test-first RED head | Confirmed: implementation module absent and frontend Check failed |
| Exact lock generation | Passed; temporary workflow deleted itself |
| UI integration run 1 | Behavior tests and build passed; new module coverage gate exposed one unreachable callback |
| Root-cause repair | Unreachable callback removed; no suppression or ignore added |
| UI integration run 2 | Passed; temporary workflow deleted itself after committing verified UI integration |
| Focused layout coverage | 100% statement, branch, function, and line gate in the successful one-shot run |
| Hostile-input RED/GREEN | Repeated IDs and locale ordering failed first; unique internal names and code-unit comparison then passed all 214 frontend tests |
| Production notice RED/GREEN | Vite bundle initially failed because `dist/THIRD_PARTY_NOTICES.md` was absent; public copy plus post-build equality verification then passed |
| Review-requested UI contracts | Successful coordinates, exact Undo restoration, and calculation failure preserving current nodes and the prior Undo boundary are directly asserted |
| Rich-node geometry RED/GREEN | Old estimate failed a comments/examples/overflow/index contract; conservative rendered-content height then passed the complete verification chain |
| Final one-shot verification | License verification, typecheck, complete tests, coverage, and production build succeeded before the workflows committed and deleted themselves |
| Existing asynchronous App test | One predecessor RED run exposed the known diagram-list timing flake; it did not reproduce on corrected heads and remains a separate test-reliability issue |
| Final documentation head | This traceability commit intentionally moves the head; all ordinary required checks and central reviews must rerun on it |
| Independent approval | Required before protected merge; not inferred from automated review |
| Shipped on `main` | No, until ordinary protected merge succeeds |

## Release and rollback boundary

Do not represent #996 as shipped until the unchanged latest head has every then-live required check in terminal success, no valid unresolved review finding, and a qualifying independent non-author approval. Queued, stale, predecessor-head, skipped-required, model-only, author-only, or local evidence is non-passing.

Rollback removes the new dependency and layout call sites, restores the fixed-grid fallback, and removes source/public/distributed notices only after the production dependency graph no longer contains the packages. Persisted node positions remain compatible because this slice does not change the saved layout schema.
