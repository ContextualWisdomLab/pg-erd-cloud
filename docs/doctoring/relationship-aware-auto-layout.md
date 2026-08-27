# Relationship-aware ERD automatic layout

## Product claim

pg-erd-cloud provides deterministic, relationship-aware **table-node placement** for ERD snapshots and the explicit `ERD 자동 정렬` action. It does not claim mathematically optimal crossing reduction, port-aware orthogonal edge routing, or stable incremental layout.

```text
PostgreSQL foreign-key evidence
→ React Flow child→parent edge
→ reversed parent→child ranking edge
→ deterministic layered node coordinates
→ existing React Flow smoothstep rendering
```

## Research basis

Layered drawing is appropriate when a directed relation should communicate precedence or dependency. The classical Sugiyama-family process separates cycle handling, layer assignment, crossing reduction, and coordinate assignment rather than treating diagram placement as a simple alphabetical grid. Dagre is a JavaScript implementation of directed-graph layout that draws on this research lineage.

The product slice uses:

- a greedy cycle breaker so cyclic schemas still receive finite coordinates;
- network-simplex ranking for layer assignment;
- locale-independent code-unit ordering;
- an index-qualified internal multigraph name for every relationship, including repeated or empty external IDs;
- measured, explicit, or conservatively estimated table dimensions;
- pre-measurement height for title comments, rendered column rows, visible comments/examples, column overflow, index sections, index rows, and index overflow;
- parent-before-child ranking derived from foreign-key direction;
- complete-result validation before publishing any new position.

Crossing minimization is computationally difficult in general, and the selected implementation is a practical heuristic system. The product therefore does not describe the result as globally optimal. Brandes and Köpf's work motivates careful horizontal coordinate assignment in layered drawings, while Barth, Mutzel, and Jünger describe bilayer crossing minimization methods within the same broader problem family. These sources explain the algorithmic domain; they do not prove that every pg-erd-cloud output is optimal.

## Product-to-code traceability

| Product requirement | Implementation | Executable evidence |
|---|---|---|
| Referenced tables precede dependent tables | FK edge is reversed only inside `computeDagreLayout` | LR and TB parent/child tests |
| Product edge semantics remain unchanged | Snapshot edges remain child `source` → parent `target` | `convertLayout.test.ts` |
| Stable result for stable input | Locale-independent code-unit sorting | reversed-input and Unicode identifier tests |
| Cyclic schema support | `acyclicer: "greedy"` | cycle regression test |
| Parallel FK support | Directed multigraph and index-qualified internal names | parallel, empty-ID, and repeated-ID tests |
| Disconnected tables | Every visible node registered before edges | disconnected-node test |
| Missing endpoint safety | Incomplete edges excluded from placement | hostile endpoint test |
| Variable and rich table dimensions | measured → explicit → conservative rendered-content estimate | dimension-source and rich-node-height tests |
| No partial coordinate corruption | Every node validated before publication | throwing and invalid-engine tests |
| One implementation for load and toolbar | `snapshotToGraph` and `App` share the same boundary | conversion and UI tests |
| Successful coordinates and exact Undo | UI exposes and compares actual node positions | `App.coverage.test.tsx` |
| Calculation failure preserves state | Checked layout throws before Undo replacement or node update | UI failure regression test |
| Commercial-use dependency boundary | Exact lock, notices, offline verifier | `verify-layout-license.mjs` and CI |
| Notice included in shipped bundle | public notice copied by Vite and compared after build | `verify-layout-distribution.mjs` |

## License and distribution evidence

The production dependency is exactly `@dagrejs/dagre` 3.1.0. Its sole runtime dependency is exactly `@dagrejs/graphlib` 4.0.3. The checked lockfile declares MIT for both. The upstream tagged releases carry the same MIT notice and copyright statement.

MIT permits commercial use, modification, distribution, sublicensing, and sale, provided the copyright and permission notice is retained in copies or substantial portions. The exact notice is preserved in:

- `frontend/THIRD_PARTY_NOTICES.md` — reviewed source authority;
- `frontend/public/THIRD_PARTY_NOTICES.md` — byte-identical Vite public artifact;
- `dist/THIRD_PARTY_NOTICES.md` — required production-build artifact.

The offline verifiers reject version drift, a non-MIT lock declaration, a changed runtime dependency graph, missing notice text, a mismatched public copy, or an omitted/mismatched production artifact. This is a bounded compliance assertion for the new layout subtree, not a legal opinion on every dependency already present in the frontend.

## TDD and verification history

1. The first PR head contained only layout contract tests and failed because `dagreLayout.ts` did not yet exist.
2. A one-shot workflow generated the exact npm lock, ran `npm ci`, typecheck, tests, and build, then deleted itself.
3. The first UI integration run passed 212 behavior tests and build but failed the new module's 100% function/statement coverage gate.
4. Root-cause analysis found an unreachable default-edge-label callback. It was removed rather than excluded or suppressed.
5. The second integration run passed 100% statement, branch, function, and line coverage for the module and deleted its one-shot workflow.
6. Self-review added RED contracts for repeated edge IDs and locale-dependent ordering. Both failed on the predecessor head as expected.
7. The GREEN fix retained every relationship with a unique internal name and switched to code-unit ordering. The next exact-head frontend Check passed all 214 tests.
8. A distribution test was added before the Vite public notice existed. All tests and the Vite bundle succeeded, but the build failed exactly because `dist/THIRD_PARTY_NOTICES.md` was absent.
9. The public notice and pre-/post-build equality checks were added; the next frontend build passed and verified the notice in the shipped artifact.
10. Code review requested UI-level state evidence. Tests now assert the applied coordinates, exact Undo coordinates, and calculation-failure preservation of current nodes and the previous Undo boundary.
11. Review also identified possible underestimation for comments, examples, overflow, and indexes. A focused geometry test first failed because the old estimate reserved only 705 pixels for the rich node.
12. The estimator was expanded to account for all rendered detail rows. A full one-shot verification then passed license verification, typecheck, the complete test suite, coverage, and production build before deleting itself.
13. A static-review formatting finding was repaired with explicit terminators and repository-consistent indentation. The workflow again required the full verification chain and committed only after success, then deleted itself.

Ordinary pull-request checks, security checks, dependency review, central model reviews, and independent human approval remain authoritative for merge readiness. Successful one-shot workflows are bounded evidence, not substitutes for protected-branch gates.

## Operational observations

Monitor these signals before broad large-schema claims:

- layout wall-clock duration by table and FK count;
- browser long-task duration;
- peak heap growth;
- coordinate validation failure count;
- user-triggered Undo after auto-layout;
- saved-view conflict rate following layout;
- difference between estimated and measured geometry.

No performance threshold is asserted until a reproducible schema corpus and browser benchmark are checked into the repository.

## Known limitations and next research questions

- React Flow `smoothstep` paths are not port-aware orthogonal routes and can cross tables or one another.
- Column handle order is not part of the Dagre ranking contract.
- Schema/domain compound nodes are not represented.
- User-pinned nodes and incremental mental-map preservation are not implemented.
- The layout runs on the browser main thread rather than a Web Worker.
- Direction is internally supported as `LR` and `TB`, but no persisted direction control is exposed.
- No screenshot-based visual regression suite or assistive-technology review has yet been recorded.

Each expansion requires a separate product contract, benchmark, license review, and ADR rather than silently widening this decision.

## References

Barth, W., Mutzel, P., & Jünger, M. (2004). Simple and efficient bilayer cross counting. *Journal of Graph Algorithms and Applications, 8*(2), 179–194. https://doi.org/10.7155/jgaa.00088

Brandes, U., & Köpf, B. (2001). Fast and simple horizontal coordinate assignment. In P. Mutzel, M. Jünger, & S. Leipert (Eds.), *Graph drawing: 9th international symposium, GD 2001* (pp. 31–44). Springer. https://doi.org/10.1007/3-540-45848-4_3

DagreJS contributors. (2026). *@dagrejs/dagre* (Version 3.1.0) [Computer software]. GitHub. https://github.com/dagrejs/dagre/tree/v3.1.0

Gansner, E. R., Koutsofios, E., North, S. C., & Vo, K.-P. (1993). A technique for drawing directed graphs. *IEEE Transactions on Software Engineering, 19*(3), 214–230. https://doi.org/10.1109/32.221135

Sugiyama, K., Tagawa, S., & Toda, M. (1981). Methods for visual understanding of hierarchical system structures. *IEEE Transactions on Systems, Man, and Cybernetics, 11*(2), 109–125. https://doi.org/10.1109/TSMC.1981.4308636
