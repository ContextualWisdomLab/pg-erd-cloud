# ADR 0001: Use pinned MIT Dagre for relationship-aware ERD node layout

- Status: Accepted for PR #996; effective when the PR is merged
- Date: 2026-08-27
- Decision owners: pg-erd-cloud maintainers
- Supersedes: the unmerged product intent of closed PR #716

## Context

The ERD canvas previously assigned tables to an alphabetical fixed grid. That layout was deterministic but ignored foreign-key topology, so referenced/master tables and dependent tables could appear in an arbitrary visual order. The toolbar's `ERD 자동 정렬` action repeated the same fixed-grid algorithm and therefore did not reduce the buyer's effort to understand a schema.

A prior Dagre pull request was closed without merge after unrelated dependency and security changes accumulated in the same branch. The layout capability remains valid, but the implementation must be reconstructed from the current `main` with a bounded dependency and review surface.

The first production slice needs relationship-aware table placement, deterministic coordinates, cycle tolerance, disconnected-component placement, a one-step undo boundary, and safe failure behavior. Precise column-port routing, obstacle-avoiding orthogonal edges, compound domain groups, and incremental pinned-node layout are separate product capabilities and must not be implied by this decision.

## Decision

Use `@dagrejs/dagre` 3.1.0 for the P0 table-node layout and accept its sole runtime dependency, `@dagrejs/graphlib` 4.0.3. Both packages are pinned exactly in `frontend/package.json` and `frontend/package-lock.json` and are licensed under the MIT License.

The implementation contract is:

1. React Flow foreign-key edges retain their product semantics: dependent child table as `source`, referenced parent table as `target`.
2. The layout graph reverses that edge only for ranking, so referenced tables precede dependent tables in left-to-right or top-to-bottom output.
3. Node and edge inputs are sorted by stable identifiers before the layout call.
4. Measured dimensions are used when available; explicit dimensions are the next source; otherwise a bounded column-count estimate is used.
5. Cycles are handled by Dagre's greedy acyclicer, while ranking uses network simplex.
6. Edges with an endpoint not present in the current node set are excluded from layout calculation rather than creating phantom nodes.
7. A thrown engine error or incomplete/non-finite geometry fails closed. Every original coordinate is preserved, and no new undo snapshot is published.
8. Snapshot conversion and the explicit toolbar action call the same pure layout boundary.
9. The existing React Flow `smoothstep` renderer remains responsible for visual edge paths. This ADR does not claim orthogonal obstacle routing or column-port optimization.

## Commercial-license boundary

The MIT License permits use, modification, distribution, sublicensing, and sale, subject to retaining the copyright and permission notice in copies or substantial portions. `frontend/THIRD_PARTY_NOTICES.md` carries the exact upstream notices for both packages.

CI runs `npm run verify:layout-license` and fails if any of the following changes without a reviewed decision:

- Dagre is not exactly 3.1.0;
- Graphlib is not exactly 4.0.3;
- either lock entry is not declared MIT;
- Dagre's reviewed runtime dependency set changes;
- Graphlib gains a runtime dependency;
- the required copyright and permission notice is missing.

GPL, AGPL, SSPL, evaluation-only, source-available, or proprietary layout software is not introduced by this decision. A later ELK, yFiles, Graphviz, or custom-routing proposal requires a separate ADR, dependency review, license review, benchmark, and migration plan.

## Alternatives considered

### Keep the alphabetical fixed grid

Rejected as the default because it does not encode foreign-key dependency direction and makes buyers manually reconstruct the schema's structural flow.

### Implement a layout engine in-house immediately

Rejected for this slice. Crossing minimization and layered coordinate assignment are mature graph-drawing problems. A new implementation would materially increase algorithmic, numerical, performance, and maintenance risk without first proving a buyer-visible advantage.

### Adopt ELK.js immediately

Deferred rather than rejected. ELK is a stronger candidate for explicit ports, compound nodes, and orthogonal routing, but those capabilities require a broader graph contract and a separate license/compliance review. Introducing that scope into the P0 node-placement slice would obscure whether the basic relationship-aware workflow is correct.

### Adopt yFiles immediately

Deferred. It offers a broad commercial graph-layout product, but it adds procurement, proprietary-license, distribution, and vendor-dependency decisions beyond the current bounded requirement.

## Consequences

### Positive

- Initial diagrams and explicit auto-layout communicate parent-to-child structure.
- Coordinates remain deterministic for a stable graph and dimensions.
- Cycles, parallel foreign keys, disconnected tables, and missing edge endpoints are covered by executable tests.
- Layout failures cannot partially overwrite saved or manually arranged coordinates.
- Commercial-use permission and required notice retention are both explicit and continuously checked.
- The pure function is independent of React rendering and can later move to a Web Worker without changing the product contract.

### Negative and residual risk

- Layered output is not a proof of globally minimal edge crossings or diagram area.
- Current edge paths are not obstacle-avoiding orthogonal routes.
- Large-schema browser latency has not yet been characterized by a published benchmark.
- Re-running layout intentionally rearranges all eligible nodes; pinned-node and incremental mental-map preservation are not implemented.
- Table dimensions estimated before measurement can differ from final rendered dimensions, although a later explicit layout uses measured sizes when React Flow provides them.

## Verification

- `frontend/src/erd/dagreLayout.test.ts`
- `frontend/src/erd/convertLayout.test.ts`
- existing `frontend/src/App.coverage.test.tsx` auto-layout and undo scenarios
- `frontend/scripts/verify-layout-license.mjs`
- repository frontend typecheck, behavior tests, coverage, and production build
- exact-head security, dependency, and independent review gates before merge

## Rollback

Rollback removes the Dagre call sites and exact dependency, restores the prior fixed-grid placement, and removes the Dagre/Graphlib notice entries only after confirming the packages are absent from the production dependency graph. Existing saved coordinates remain valid because the persisted node-position schema is unchanged.
