# Relationship-aware ERD layout

Status: **Implemented** for browser snapshot import and the explicit toolbar
action. This is a deterministic presentation contract; it does not alter stored
schema metadata, relationship authority, or server-side forward engineering.

## User outcome

Imported ERDs and explicit auto-layout use the same left-to-right Dagre graph
contract instead of an alphabetical fixed grid. Foreign-key edges influence
rank placement, while cycles and disconnected components remain supported.

The pure `computeDagreLayout` helper:

- accepts React Flow nodes, edges, and `LR` or `TB` direction;
- prefers measured node rectangles and otherwise uses conservative table-size
  estimates based on visible columns and indexes;
- converts Dagre center coordinates to React Flow top-left coordinates;
- ignores edges whose source or target node is absent;
- inserts nodes and edges in a stable order for repeatable output;
- returns new node objects without mutating either input collection; and
- preserves the prior coordinate of every node if Dagre throws or returns
  missing or non-finite geometry.

The toolbar captures positions before the layout and keeps exactly one undo
snapshot. Nodes added after layout are not removed by undo. Dagre failures do
not move nodes; handler-level failures continue to use the existing polite live
region.

## Verification contract

Focused unit coverage includes empty and single-direction graphs, LR and TB,
cycles, disconnected components, dangling endpoints, measured rectangles,
determinism, non-overlap, input immutability, and engine failure. Application
coverage proves the toolbar changes coordinates and restores the exact prior
coordinates in one undo. Snapshot conversion verifies that the same
relationship-aware contract supplies initial positions.

## Limitations

The layout is local browser presentation. It does not persist coordinates to a
diagram view, perform collaborative conflict resolution, or guarantee the
global optimum for every graph. Very large diagrams still require browser
performance evidence before a scalability claim.

## Research and dependency traceability

The implementation pins `@dagrejs/dagre` 3.1.0 exactly in the canonical npm
manifest and lockfile. The algorithmic basis is the directed-graph ranking and
crossing-minimization approach described by Gansner et al. The paper is cited
and linked rather than vendored because this repository has no recorded
redistribution permission for the publisher PDF.

- Dagre Project. (2026). *Dagre* (Version 3.1.0) [Computer software].
  https://github.com/dagrejs/dagre
- Gansner, E. R., Koutsofios, E., North, S. C., & Vo, K.-P. (1993). A
  technique for drawing directed graphs. *IEEE Transactions on Software
  Engineering, 19*(3), 214-230. https://doi.org/10.1109/32.221135
