import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import { inferRelationships } from "../autoInfer";
import type { TableNodeData } from "../convert";

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
      relation_name: title.split(".").slice(1).join("."), // mock exact relation_name propagation
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
      tableNode("dotted_target", "public.Order.Items", [
        { column_name: "id", data_type: "bigint", is_not_null: true, is_pk: true },
      ]),
      tableNode("dotted_source", "public.Order.Audit", [
        {
          column_name: "Order.Items_id",
          data_type: "bigint",
          is_not_null: true,
          is_pk: false,
        },
      ]),
    ];

    const edges = inferRelationships(nodes);

    expect(edges).toHaveLength(3);
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
    expect(
      edges.find((edge) => edge.source === "dotted_source"),
    ).toMatchObject({
      target: "dotted_target",
      data: {
        sourceColumns: ["Order.Items_id"],
        targetColumns: ["id"],
      },
    });
  });

  it("supports dotted legacy names with singular, plural, and -es fallbacks", () => {
    const target = (id: string, title: string): Node<TableNodeData> =>
      tableNode(id, title, [{ column_name: "id", data_type: "integer", is_not_null: true, is_pk: true }]);
    const source = (id: string, columnName: string): Node<TableNodeData> =>
      tableNode(id, "public.audit", [{ column_name: columnName, data_type: "integer", is_not_null: true, is_pk: false }]);

    expect(inferRelationships([target("singular", "legacy.Widget"), source("singular_source", "schema.Widget_id")])).toHaveLength(1);
    expect(inferRelationships([target("plural", "legacy.Widgets"), source("plural_source", "schema.Widget_id")])).toHaveLength(1);
    expect(inferRelationships([target("es", "legacy.Boxes"), source("es_source", "schema.Box_id")])).toHaveLength(1);
  });
});
