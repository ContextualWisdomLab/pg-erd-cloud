import { describe, it, expect } from "vitest";
import { exportPrisma } from "../prisma";
import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "../convert";

describe("exportPrisma edge cases", () => {
  it("handles edges with malformed source and target handles", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "A",
        position: { x: 0, y: 0 },
        data: {
          title: "TableA",
          columns: [{ column_name: "id", data_type: "integer", is_pk: true, is_not_null: true }],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: "B",
        position: { x: 0, y: 0 },
        data: {
          title: "TableB",
          columns: [{ column_name: "invalid-source", data_type: "integer", is_pk: false, is_not_null: true }],
          badges: { pk: false, fk: false },
        },
      },
    ];

    const edges: Edge[] = [
      {
        id: "e1",
        source: "B",
        target: "A",
        // Malformed handles (don't start with src- or tgt-)
        sourceHandle: "invalid-source",
        targetHandle: "invalid-target",
      },
    ];

    const result = exportPrisma(nodes, edges);
    expect(result).toContain('model TableB {');
  });

  it("handles incoming relations when they are empty", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "Isolated",
        position: { x: 0, y: 0 },
        data: {
          title: "Isolated",
          columns: [{ column_name: "id", data_type: "integer", is_pk: true, is_not_null: true }],
          badges: { pk: true, fk: false },
        },
      },
    ];

    const result = exportPrisma(nodes, []);
    expect(result).toContain('model Isolated {');
    expect(result).not.toContain('@relation');
  });
});
