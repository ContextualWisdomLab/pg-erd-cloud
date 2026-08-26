import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { inferRelationships } from "../autoInfer";
import type { TableNodeData } from "../convert";

function tableNode(
  id: string,
  title: string,
  relationName: string,
  columns: TableNodeData["columns"],
): Node<TableNodeData> {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      title,
      relation_name: relationName,
      columns,
      badges: {
        pk: columns.some((column) => column.is_pk),
        fk: columns.some((column) => column.column_name.endsWith("_id")),
      },
    },
  };
}

describe("inferRelationships PostgreSQL identifier fidelity", () => {
  it("preserves Unicode, spaces, mixed case, and periods in relation identity", () => {
    const nodes: Node<TableNodeData>[] = [
      tableNode("unicode_target", "public.사용자", "사용자", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("unicode_source", "public.활동", "활동", [
        { column_name: "사용자_id", data_type: "bigint", is_not_null: true, is_pk: false },
      ]),
      tableNode("quoted_target", "public.Order Items", "Order Items", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("quoted_source", "public.Order Audit", "Order Audit", [
        { column_name: "Order Items_id", data_type: "bigint", is_not_null: true, is_pk: false },
      ]),
      tableNode("dotted_target", "public.Order.Items", "Order.Items", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("dotted_source", "public.Order.Audit", "Order.Audit", [
        { column_name: "Order.Items_id", data_type: "bigint", is_not_null: true, is_pk: false },
      ]),
    ];

    const edges = inferRelationships(nodes);

    expect(edges).toHaveLength(3);
    expect(edges.find((edge) => edge.source === "unicode_source")).toMatchObject({
      target: "unicode_target",
      data: { sourceColumns: ["사용자_id"], targetColumns: ["id"] },
    });
    expect(edges.find((edge) => edge.source === "quoted_source")).toMatchObject({
      target: "quoted_target",
      data: { sourceColumns: ["Order Items_id"], targetColumns: ["id"] },
    });
    expect(edges.find((edge) => edge.source === "dotted_source")).toMatchObject({
      target: "dotted_target",
      data: { sourceColumns: ["Order.Items_id"], targetColumns: ["id"] },
    });
  });

  it("does not alias a dotted relation to its trailing identifier segment", () => {
    const nodes: Node<TableNodeData>[] = [
      tableNode("dotted_target", "public.Order.Items", "Order.Items", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("plain_target", "public.Items", "Items", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("source", "public.Audit", "Audit", [
        { column_name: "Items_id", data_type: "bigint", is_not_null: true, is_pk: false },
      ]),
    ];

    expect(inferRelationships(nodes)).toContainEqual(
      expect.objectContaining({ source: "source", target: "plain_target" }),
    );
  });
});
