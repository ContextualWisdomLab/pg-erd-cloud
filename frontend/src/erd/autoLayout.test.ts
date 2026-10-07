import { describe, it, expect } from "vitest";
import { computeDagreLayout } from "./autoLayout";
import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";

describe("computeDagreLayout", () => {
  it("should position nodes correctly using dagre layout", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "1",
        type: "tableNode",
        position: { x: 0, y: 0 },
        data: {
          title: "users",
          columns: [
            { column_name: "id", data_type: "int", is_not_null: true, is_pk: true },
          ],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: "2",
        type: "tableNode",
        position: { x: 0, y: 0 },
        data: {
          title: "posts",
          columns: [
            { column_name: "id", data_type: "int", is_not_null: true, is_pk: true },
            { column_name: "user_id", data_type: "int", is_not_null: true, is_pk: false },
          ],
          badges: { pk: true, fk: true },
        },
      },
    ];

    const edges: Edge[] = [
      {
        id: "e1-2",
        source: "1",
        target: "2",
      },
    ];

    const positionedNodes = computeDagreLayout(nodes, edges);

    expect(positionedNodes).toHaveLength(2);
    // Nodes should have new positions assigned by dagre
    expect(positionedNodes[0].position.x).toBeDefined();
    expect(positionedNodes[0].position.y).toBeDefined();
    expect(positionedNodes[1].position.x).toBeDefined();
    expect(positionedNodes[1].position.y).toBeDefined();

    // Since users is the source and we use LR layout by default
    // users x position should be less than posts x position
    expect(positionedNodes[0].position.x).toBeLessThan(positionedNodes[1].position.x);
  });
});
