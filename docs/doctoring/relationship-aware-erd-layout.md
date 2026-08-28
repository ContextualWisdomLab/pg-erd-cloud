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
- prefers measured node rectangles; before measurement, it uses the rendered
  table component's fixed 280 px width and estimates height from the bounded
  visible columns and indexes;
- converts Dagre center coordinates to React Flow top-left coordinates;
- ignores edges whose source or target node is absent;
- inserts nodes and edges in a stable order for repeatable output;
- returns new node objects without mutating either input collection; and
- throws a bounded layout error if Dagre throws or returns missing/non-finite
  geometry so interactive callers cannot report false success.

The toolbar captures the current positions locally before attempting layout but
publishes that snapshot as the one-step undo target only after Dagre succeeds.
Nodes added after a successful layout are not removed by undo. A Dagre or
animation-frame failure is caught before new node positions are applied, so the
current diagram remains unchanged, the undo control is not armed for a no-op,
and the existing polite live region tells the customer that layout failed and
to retry. Snapshot import has a separate fail-safe boundary: if layout fails
there, the deterministic fixed grid created during conversion is retained so
the imported schema remains usable rather than failing to render.

Supported snapshot navigation clears the current graph before loading a new
snapshot. Polling an already-open snapshot preserves id-matched positions so a
background refresh does not unexpectedly rearrange a diagram the customer has
already moved or auto-laid out.

## Verification contract

Focused unit coverage includes empty and single-direction graphs, LR and TB,
cycles, disconnected components, dangling endpoints, measured rectangles,
determinism, non-overlap, input immutability, invalid geometry, top-left
overflow, and engine failure. Application coverage proves the toolbar changes
coordinates, reports handler failures through its live region, leaves undo
disabled after a failed layout, and restores the exact prior coordinates after
a successful layout. Snapshot conversion additionally covers the
deterministic-grid fallback when Dagre fails.

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
  Engineering, 19*(3), 214–230. https://doi.org/10.1109/32.221135
