# Relationship-aware ERD automatic layout

## Product claim

pg-erd-cloud provides deterministic, relationship-aware **table-node placement** for ERD snapshots and the explicit `ERD 자동 정렬` action. It does not claim mathematically optimal crossing reduction, port-aware orthogonal edge routing, or stable incremental layout.

The implementation is intentionally narrower than a full graph-drawing platform:

```text
PostgreSQL foreign-key evidence
→ React Flow child→parent edge
→ reversed parent→child ranking edge
→ deterministic layered node coordinates
→ existing React Flow smoothstep rendering
```

## Research basis

Layered drawing is appropriate when a directed relation should communicate precedence or dependency. The classical Sugiyama-family process separates cycle handling, layer assignment, crossing reduction, and coordinate assignment rather than treating diagram placement as a simple alphabetical grid. Dagre is a JavaScript implementation of directed-graph layout that draws on this research lineage.

The current product slice uses:

- a greedy cycle breaker so cyclic schemas still receive finite coordinates;
- network-simplex ranking for layer assignment;
- stable node/edge ordering before invocation;
- measured or bounded estimated table dimensions;
- parent-before-child ranking derived from foreign-key direction;
- complete-result validation before publishing any new position.

Crossing minimization is computationally difficult in general, and the selected implementation is a practical heuristic system. The product therefore does not describe the result as globally optimal. Brandes and Köpf's work motivates careful horizontal coordinate assignment in layered drawings, while Barth, Mutzel, and Jünger describe bilayer crossing minimization methods within the same broader problem family. These sources explain the algorithmic domain; they do not prove that every pg-erd-cloud output is optimal.

## Product-to-code traceability

| Product requirement | Implementation | Executable evidence |
|---|---|---|
| Referenced tables precede dependent tables | Foreign-key edge is reversed only inside `computeDagreLayout` | LR and TB parent/child tests |
| Product edge semantics remain unchanged | Snapshot edges stay child `source` → parent `target` | `convertLayout.test.ts` |
| Stable result for stable input | Nodes and edges sorted by stable identifiers | reversed-input determinism test |
| Cyclic schema support | `acyclicer: "greedy"` | cycle regression test |
| Parallel FK support | directed multigraph and stable edge names | parallel-edge regression test |
| Disconnected tables | all visible nodes registered before edges | disconnected-node regression test |
| Missing endpoint safety | incomplete edges ignored for placement | hostile endpoint regression test |
| Variable table dimensions | measured → explicit → bounded estimate | dimension-source regression test |
| No partial coordinate corruption | validate every node before publishing | throwing and invalid-engine tests |
| One implementation for load and toolbar | `snapshotToGraph` and `App` share the same boundary | conversion and UI tests |
| One-step undo only after success | undo snapshot written after checked layout returns | existing App coverage scenarios |
| Commercial-use dependency boundary | exact lock, notice, offline verifier | `verify-layout-license.mjs` and CI |

## License and distribution evidence

The production dependency is exactly `@dagrejs/dagre` 3.1.0. Its sole runtime dependency is exactly `@dagrejs/graphlib` 4.0.3. The checked lockfile declares MIT for both. The upstream tagged releases carry the same MIT notice and copyright statement.

MIT permits commercial use, modification, distribution, sublicensing, and sale, provided the copyright and permission notice is retained in copies or substantial portions. The exact notices are preserved in `frontend/THIRD_PARTY_NOTICES.md`.

The offline CI verifier rejects:

- version drift;
- a non-MIT lock declaration;
- a new Dagre runtime dependency;
- any Graphlib runtime dependency;
- removal of the required notice text.

This is a bounded compliance assertion for the new layout subtree. It is not a legal opinion on every dependency already present in the frontend.

## TDD and verification history

1. The first PR head contained only the layout contract tests and failed because `dagreLayout.ts` did not yet exist.
2. The implementation was added only after that RED evidence.
3. A one-shot workflow generated the exact npm lock, installed it with `npm ci`, ran type checking, behavior tests, and a production build, then deleted itself.
4. The first UI integration run passed 212 tests and the build but failed the new module's 100% function/statement coverage gate.
5. Root-cause analysis found an unreachable default-edge-label callback: every edge already supplied an explicit label object. The unused callback was removed rather than excluded or suppressed.
6. The second integration run passed the exact coverage gate and deleted its one-shot workflow after committing the verified UI integration.

Repository pull-request checks, security checks, dependency review, and independent review remain authoritative for merge readiness. A successful one-shot workflow is evidence for the bounded change, not a substitute for protected-branch gates.

## Operational observations

Monitor these signals before broad large-schema claims:

- layout wall-clock duration by table and FK count;
- browser long-task duration;
- peak heap growth;
- coordinate validation failure count;
- user-triggered undo after auto-layout;
- saved-view conflict rate following layout;
- difference between pre-measurement and post-measurement coordinates.

No performance threshold is asserted until a reproducible schema corpus and browser benchmark are checked into the repository.

## Known limitations and next research questions

- React Flow `smoothstep` paths are not port-aware orthogonal routes and can cross tables or one another.
- Column handle order is not part of the Dagre ranking contract.
- Schema/domain compound nodes are not represented.
- User-pinned nodes and incremental mental-map preservation are not implemented.
- The layout runs on the browser main thread rather than a Web Worker.
- Direction is internally supported as `LR` and `TB`, but the product does not yet expose a persisted direction control.
- No screenshot-based visual regression suite or assistive-technology review has yet been recorded for the new geometry.

Each expansion requires a separate product contract, benchmark, license review, and ADR rather than silently widening this decision.

## References

Barth, W., Mutzel, P., & Jünger, M. (2004). Simple and efficient bilayer cross counting. *Journal of Graph Algorithms and Applications, 8*(2), 179–194. https://doi.org/10.7155/jgaa.00088

Brandes, U., & Köpf, B. (2001). Fast and simple horizontal coordinate assignment. In P. Mutzel, M. Jünger, & S. Leipert (Eds.), *Graph drawing: 9th international symposium, GD 2001* (pp. 31–44). Springer. https://doi.org/10.1007/3-540-45848-4_3

DagreJS contributors. (2026). *@dagrejs/dagre* (Version 3.1.0) [Computer software]. GitHub. https://github.com/dagrejs/dagre/tree/v3.1.0

Gansner, E. R., Koutsofios, E., North, S. C., & Vo, K.-P. (1993). A technique for drawing directed graphs. *IEEE Transactions on Software Engineering, 19*(3), 214–230. https://doi.org/10.1109/32.221135

Sugiyama, K., Tagawa, S., & Toda, M. (1981). Methods for visual understanding of hierarchical system structures. *IEEE Transactions on Systems, Man, and Cybernetics, 11*(2), 109–125. https://doi.org/10.1109/TSMC.1981.4308636
