import { layout as runDagreLayout } from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import {
  computeDagreLayout,
  requireDagreLayout,
  type DagreLayoutEngine,
} from "./dagreLayout";
import type { TableNodeData } from "./convert";

function tableNode(
  id: string,
  position = { x: 0, y: 0 },
  columnCount = 0,
): Node<TableNodeData> {
  return {
    id,
    type: "tableNode",
    position,
    data: {
      title: `public.${id}`,
      columns: Array.from({ length: columnCount }, (_, index) => ({
        column_name: `column_${index}`,
        data_type: "text",
        is_not_null: false,
        is_pk: false,
      })),
      badges: { pk: false, fk: false },
    },
  };
}

function positionsById(nodes: Array<Node<TableNodeData>>) {
  return Object.fromEntries(
    nodes.map((node) => [node.id, { ...node.position }]),
  );
}

describe("computeDagreLayout", () => {
  it("returns an applied empty result without mutating input", () => {
    const nodes: Array<Node<TableNodeData>> = [];

    const result = computeDagreLayout(nodes, []);

    expect(result).toEqual({ applied: true, nodes: [] });
    expect(nodes).toEqual([]);
  });

  it("places referenced parent tables before dependent children in LR mode", () => {
    const nodes = [tableNode("child"), tableNode("parent")];
    const edges: Edge[] = [
      { id: "fk_child_parent", source: "child", target: "parent" },
    ];

    const result = computeDagreLayout(nodes, edges, "LR");
    const positions = positionsById(result.nodes);

    expect(result.applied).toBe(true);
    expect(positions.parent.x).toBeLessThan(positions.child.x);
    expect(result.nodes.map((node) => node.id)).toEqual(["child", "parent"]);
  });

  it("places referenced parent tables above dependent children in TB mode", () => {
    const nodes = [tableNode("parent"), tableNode("child")];
    const edges: Edge[] = [
      { id: "fk_child_parent", source: "child", target: "parent" },
    ];

    const result = computeDagreLayout(nodes, edges, "TB");
    const positions = positionsById(result.nodes);

    expect(result.applied).toBe(true);
    expect(positions.parent.y).toBeLessThan(positions.child.y);
  });

  it("lays out disconnected, cyclic, and parallel relationships with finite non-overlapping coordinates", () => {
    const nodes = [
      tableNode("alpha", { x: 9, y: 9 }, 2),
      tableNode("beta", { x: 9, y: 9 }, 6),
      tableNode("gamma", { x: 9, y: 9 }, 1),
      tableNode("isolated", { x: 9, y: 9 }),
    ];
    const edges: Edge[] = [
      { id: "alpha_beta_1", source: "alpha", target: "beta" },
      { id: "", source: "alpha", target: "beta" },
      { id: "beta_gamma", source: "beta", target: "gamma" },
      { id: "gamma_alpha", source: "gamma", target: "alpha" },
      { id: "missing", source: "missing", target: "alpha" },
    ];
    const original = structuredClone(nodes);

    const result = computeDagreLayout(nodes, edges);
    const coordinateKeys = result.nodes.map(
      (node) => `${node.position.x}:${node.position.y}`,
    );

    expect(result.applied).toBe(true);
    expect(nodes).toEqual(original);
    expect(result.nodes).not.toBe(nodes);
    expect(result.nodes.every((node) => Number.isFinite(node.position.x))).toBe(
      true,
    );
    expect(result.nodes.every((node) => Number.isFinite(node.position.y))).toBe(
      true,
    );
    expect(new Set(coordinateKeys).size).toBe(nodes.length);
  });

  it("preserves parallel relationships even when hostile input repeats an edge id", () => {
    const nodes = [tableNode("parent"), tableNode("child")];
    const edges: Edge[] = [
      { id: "duplicate", source: "child", target: "parent" },
      { id: "duplicate", source: "child", target: "parent" },
    ];
    const inspectingEngine: DagreLayoutEngine = (graph) => {
      expect(graph.edgeCount()).toBe(2);
      runDagreLayout(graph);
    };

    const result = computeDagreLayout(nodes, edges, "LR", inspectingEngine);

    expect(result.applied).toBe(true);
  });

  it("registers identifiers in locale-independent code-unit order", () => {
    const nodes = [tableNode("ä"), tableNode("z"), tableNode("A")];
    const inspectingEngine: DagreLayoutEngine = (graph) => {
      expect(graph.nodes()).toEqual(["A", "z", "ä"]);
      runDagreLayout(graph);
    };

    const result = computeDagreLayout(nodes, [], "LR", inspectingEngine);

    expect(result.applied).toBe(true);
  });

  it("is deterministic regardless of input node and edge order", () => {
    const nodes = [tableNode("child"), tableNode("parent"), tableNode("audit")];
    const edges: Edge[] = [
      { id: "fk_child_parent", source: "child", target: "parent" },
      { id: "fk_audit_parent", source: "audit", target: "parent" },
    ];

    const forward = computeDagreLayout(nodes, edges);
    const reversed = computeDagreLayout(
      [...nodes].reverse(),
      [...edges].reverse(),
    );

    expect(positionsById(forward.nodes)).toEqual(positionsById(reversed.nodes));
  });

  it("uses measured and explicit dimensions while estimating missing metadata", () => {
    const measured = tableNode("measured");
    const explicit = tableNode("explicit");
    const minimal: Node<{ columns?: readonly unknown[] }> = {
      id: "minimal",
      position: { x: 0, y: 0 },
      data: {},
    };
    measured.measured = { width: 600, height: 300 };
    explicit.width = 420;
    explicit.height = 180;

    const result = computeDagreLayout(
      [measured, explicit, minimal],
      [],
      "LR",
    );

    expect(result.applied).toBe(true);
    expect(new Set(result.nodes.map((node) => node.position.x)).size).toBe(3);
  });

  it("fails closed and preserves every position when the layout engine throws", () => {
    const nodes = [
      tableNode("one", { x: 125, y: 225 }),
      tableNode("two", { x: 325, y: 425 }),
    ];
    const failingEngine: DagreLayoutEngine = () => {
      throw new Error("layout failure");
    };

    const result = computeDagreLayout(nodes, [], "LR", failingEngine);

    expect(result).toEqual({
      applied: false,
      nodes: structuredClone(nodes),
      reason: "layout_error",
    });
  });

  it("fails closed when the engine returns incomplete or non-finite geometry", () => {
    const nodes = [tableNode("one", { x: 44, y: 55 })];
    const invalidEngine: DagreLayoutEngine = () => undefined;

    const result = computeDagreLayout(nodes, [], "LR", invalidEngine);

    expect(result).toEqual({
      applied: false,
      nodes: structuredClone(nodes),
      reason: "invalid_geometry",
    });
  });
});

describe("requireDagreLayout", () => {
  it("returns the applied node set", () => {
    const nodes = [tableNode("parent"), tableNode("child")];

    const result = requireDagreLayout(nodes, [
      { id: "fk", source: "child", target: "parent" },
    ]);

    expect(result).toHaveLength(2);
    expect(positionsById(result).parent.x).toBeLessThan(
      positionsById(result).child.x,
    );
  });

  it("throws the fail-closed reason for an invalid engine result", () => {
    const invalidEngine: DagreLayoutEngine = () => undefined;

    expect(() =>
      requireDagreLayout([tableNode("one")], [], "LR", invalidEngine),
    ).toThrow("Dagre layout failed: invalid_geometry");
  });
});
