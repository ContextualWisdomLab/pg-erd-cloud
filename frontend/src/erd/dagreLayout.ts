import { Graph, layout as runDagreLayout } from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

const DEFAULT_NODE_WIDTH = 280;
const BASE_NODE_HEIGHT = 80;
const COLUMN_ROW_HEIGHT = 25;
const MAX_RENDERED_COLUMNS = 25;
const NODE_SEPARATION = 60;
const RANK_SEPARATION = 120;
const EDGE_SEPARATION = 24;
const LAYOUT_MARGIN = 24;

type LayoutNodeData = {
  columns?: readonly unknown[];
};

type DagreNodeGeometry = {
  width: number;
  height: number;
  x?: number;
  y?: number;
};

export type LayoutDirection = "LR" | "TB";
export type LayoutFailureReason = "layout_error" | "invalid_geometry";
export type DagreLayoutEngine = (graph: Graph) => void;

export type DagreLayoutResult<T extends LayoutNodeData> =
  | { applied: true; nodes: Array<Node<T>> }
  | {
      applied: false;
      nodes: Array<Node<T>>;
      reason: LayoutFailureReason;
    };

function cloneNodes<T extends LayoutNodeData>(
  nodes: Array<Node<T>>,
): Array<Node<T>> {
  return nodes.map((node) => ({
    ...node,
    position: { ...node.position },
  }));
}

function positiveFinite(value: number | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function nodeDimensions<T extends LayoutNodeData>(node: Node<T>): {
  width: number;
  height: number;
} {
  const measuredWidth = node.measured?.width;
  const measuredHeight = node.measured?.height;
  const width = positiveFinite(measuredWidth)
    ? measuredWidth
    : positiveFinite(node.width)
      ? node.width
      : DEFAULT_NODE_WIDTH;
  const renderedColumnCount = Math.min(
    node.data.columns?.length ?? 0,
    MAX_RENDERED_COLUMNS,
  );
  const estimatedHeight =
    BASE_NODE_HEIGHT + renderedColumnCount * COLUMN_ROW_HEIGHT;
  const height = positiveFinite(measuredHeight)
    ? measuredHeight
    : positiveFinite(node.height)
      ? node.height
      : estimatedHeight;

  return { width, height };
}

function validGeometry(
  geometry: DagreNodeGeometry | undefined,
): geometry is Required<DagreNodeGeometry> {
  return Boolean(
    geometry &&
      positiveFinite(geometry.width) &&
      positiveFinite(geometry.height) &&
      Number.isFinite(geometry.x) &&
      Number.isFinite(geometry.y),
  );
}

/**
 * Computes a deterministic hierarchical ERD layout without mutating inputs.
 *
 * Foreign-key edges in pg-erd-cloud point from the dependent child table to
 * the referenced parent table. Dagre receives those edges in reverse solely
 * for ranking, so parent/master tables appear before their dependants. The
 * returned React Flow edges are never modified.
 *
 * When the engine throws or any node lacks complete finite geometry, the
 * operation fails closed and returns fresh node objects at every original
 * coordinate. This prevents a partially computed layout from corrupting a
 * saved or manually arranged diagram.
 */
export function computeDagreLayout<T extends LayoutNodeData>(
  nodes: Array<Node<T>>,
  edges: Edge[],
  direction: LayoutDirection = "LR",
  layoutEngine: DagreLayoutEngine = runDagreLayout,
): DagreLayoutResult<T> {
  if (nodes.length === 0) {
    return { applied: true, nodes: [] };
  }

  const graph = new Graph({ directed: true, multigraph: true });
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: direction,
    align: "UL",
    ranker: "network-simplex",
    acyclicer: "greedy",
    nodesep: NODE_SEPARATION,
    ranksep: RANK_SEPARATION,
    edgesep: EDGE_SEPARATION,
    marginx: LAYOUT_MARGIN,
    marginy: LAYOUT_MARGIN,
  });

  const sortedNodes = [...nodes].sort((left, right) =>
    left.id.localeCompare(right.id, "en"),
  );
  for (const node of sortedNodes) {
    graph.setNode(node.id, nodeDimensions(node));
  }

  const sortedEdges = [...edges].sort((left, right) => {
    const leftKey = `${left.target}\u0000${left.source}\u0000${left.id}`;
    const rightKey = `${right.target}\u0000${right.source}\u0000${right.id}`;
    return leftKey.localeCompare(rightKey, "en");
  });
  for (const [index, edge] of sortedEdges.entries()) {
    if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) {
      continue;
    }
    const edgeName = edge.id || `${edge.target}:${edge.source}:${index}`;
    graph.setEdge(edge.target, edge.source, {}, edgeName);
  }

  try {
    layoutEngine(graph);
  } catch {
    return {
      applied: false,
      nodes: cloneNodes(nodes),
      reason: "layout_error",
    };
  }

  const geometries = new Map<string, Required<DagreNodeGeometry>>();
  for (const node of nodes) {
    const geometry = graph.node(node.id) as DagreNodeGeometry | undefined;
    if (!validGeometry(geometry)) {
      return {
        applied: false,
        nodes: cloneNodes(nodes),
        reason: "invalid_geometry",
      };
    }
    geometries.set(node.id, geometry);
  }

  return {
    applied: true,
    nodes: nodes.map((node) => {
      const geometry = geometries.get(node.id)!;
      return {
        ...node,
        position: {
          x: geometry.x - geometry.width / 2,
          y: geometry.y - geometry.height / 2,
        },
      };
    }),
  };
}

/**
 * Returns a successfully computed layout or throws for the caller's existing
 * error boundary. This keeps React UI control flow simple while preserving the
 * fail-closed result contract for snapshot conversion and other batch callers.
 */
export function requireDagreLayout<T extends LayoutNodeData>(
  nodes: Array<Node<T>>,
  edges: Edge[],
  direction: LayoutDirection = "LR",
  layoutEngine: DagreLayoutEngine = runDagreLayout,
): Array<Node<T>> {
  const result = computeDagreLayout(nodes, edges, direction, layoutEngine);
  if (!result.applied) {
    throw new Error(`Dagre layout failed: ${result.reason}`);
  }
  return result.nodes;
}
