import { describe, it, expect } from "vitest";
import { computeDagreLayout } from "./layout";
import type { Node, Edge } from "@xyflow/react";

describe("computeDagreLayout", () => {
  it("should return empty array if nodes are empty", () => {
    const result = computeDagreLayout([], []);
    expect(result).toEqual([]);
  });

  it("should compute positions for nodes without edges", () => {
    const nodes: Node[] = [
      { id: "node1", position: { x: 0, y: 0 }, data: { title: "Node 1" } },
      { id: "node2", position: { x: 0, y: 0 }, data: { title: "Node 2" } },
    ];

    const result = computeDagreLayout(nodes, []);

    expect(result.length).toBe(2);
    // Nodes should have new positions assigned by dagre
    expect(result[0].position.x).toBeTypeOf("number");
    expect(result[0].position.y).toBeTypeOf("number");
    expect(result[1].position.x).toBeTypeOf("number");
    expect(result[1].position.y).toBeTypeOf("number");

    // Y position might be similar if they are in the same rank,
    // but they shouldn't be exactly overlapping at 0,0 anymore
    expect(
      result[0].position.x === 0 &&
        result[0].position.y === 0 &&
        result[1].position.x === 0 &&
        result[1].position.y === 0,
    ).toBe(false);
  });

  it("should compute positions considering edges", () => {
    const nodes: Node[] = [
      {
        id: "parent",
        position: { x: 0, y: 0 },
        data: { title: "Parent" },
        measured: { width: 100, height: 100 },
      },
      {
        id: "child",
        position: { x: 0, y: 0 },
        data: { title: "Child" },
        measured: { width: 100, height: 100 },
      },
    ];

    const edges: Edge[] = [{ id: "e1", source: "parent", target: "child" }];

    const resultTB = computeDagreLayout(nodes, edges, "TB");

    // In TB layout, parent should be above child (y coordinate should be smaller)
    const parentNode = resultTB.find((n) => n.id === "parent");
    const childNode = resultTB.find((n) => n.id === "child");

    expect(parentNode).toBeDefined();
    expect(childNode).toBeDefined();

    if (parentNode && childNode) {
      expect(parentNode.position.y).toBeLessThan(childNode.position.y);
    }
  });

  it("should handle LR direction", () => {
    const nodes: Node[] = [
      { id: "left", position: { x: 0, y: 0 }, data: { title: "Left" } },
      { id: "right", position: { x: 0, y: 0 }, data: { title: "Right" } },
    ];

    const edges: Edge[] = [{ id: "e1", source: "left", target: "right" }];

    const resultLR = computeDagreLayout(nodes, edges, "LR");

    // In LR layout, left node should be to the left of right node (x coordinate should be smaller)
    const leftNode = resultLR.find((n) => n.id === "left");
    const rightNode = resultLR.find((n) => n.id === "right");

    expect(leftNode).toBeDefined();
    expect(rightNode).toBeDefined();

    if (leftNode && rightNode) {
      expect(leftNode.position.x).toBeLessThan(rightNode.position.x);
    }
  });

  it("should ignore edges pointing to missing nodes", () => {
    const nodes: Node[] = [
      { id: "node1", position: { x: 0, y: 0 }, data: { title: "Node 1" } },
    ];

    const edges: Edge[] = [
      { id: "e1", source: "node1", target: "missing_node" },
    ];

    const result = computeDagreLayout(nodes, edges);
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("node1");
    // Should not crash when edge references a non-existent node
  });
});
