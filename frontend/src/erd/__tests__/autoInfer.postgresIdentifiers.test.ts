import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { inferRelationships } from "../autoInfer";
import { snapshotToGraph, type TableNodeData } from "../convert";
import type { SnapshotJson } from "../../types";

function tableNode(
  id: string,
  title: string,
  columns: TableNodeData["columns"],
): Node<TableNodeData> {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      title,
      columns,
      badges: {
        pk: columns.some((column) => column.is_pk),
        fk: columns.some((column) => column.column_name.endsWith("_id")),
      },
    },
  };
}

describe("inferRelationships PostgreSQL identifier fidelity", () => {
  it("matches Unicode and quoted-style table names without lossy sanitization", () => {
    const nodes: Node<TableNodeData>[] = [
      tableNode("unicode_target", "public.사용자", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("unicode_source", "public.활동", [
        {
          column_name: "사용자_id",
          data_type: "bigint",
          is_not_null: true,
          is_pk: false,
        },
      ]),
      tableNode("quoted_target", "public.Order Items", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("quoted_source", "public.Order Audit", [
        {
          column_name: "Order Items_id",
          data_type: "bigint",
          is_not_null: true,
          is_pk: false,
        },
      ]),
    ];

    const edges = inferRelationships(nodes);

    expect(edges).toHaveLength(2);
    expect(
      edges.find((edge) => edge.source === "unicode_source"),
    ).toMatchObject({
      target: "unicode_target",
      data: {
        sourceColumns: ["사용자_id"],
        targetColumns: ["id"],
      },
    });
    expect(
      edges.find((edge) => edge.source === "quoted_source"),
    ).toMatchObject({
      target: "quoted_target",
      data: {
        sourceColumns: ["Order Items_id"],
        targetColumns: ["id"],
      },
    });
  });

  it("preserves dots in quoted relation names from a database snapshot", () => {
    const snapshot: SnapshotJson = {
      relations: [
        { relation_oid: 1, relation_kind: "r", schema_name: "public", relation_name: "Order.Items" },
        { relation_oid: 2, relation_kind: "r", schema_name: "public", relation_name: "Order Audit" },
      ],
      columns: [
        { relation_oid: 1, column_name: "id", data_type: "bigint", is_not_null: true },
        { relation_oid: 2, column_name: "Order.Items_id", data_type: "bigint", is_not_null: true },
      ],
      pk_columns: [{ relation_oid: 1, column_name: "id" }],
    };

    const { nodes } = snapshotToGraph(snapshot);
    const edges = inferRelationships(nodes);

    expect(edges).toMatchObject([
      {
        source: "2",
        target: "1",
        data: { sourceColumns: ["Order.Items_id"], targetColumns: ["id"] },
      },
    ]);
  });
});
