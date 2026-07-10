import { describe, it, expect } from "vitest";
import { inferRelationships } from "../autoInfer";
import type { Node } from "@xyflow/react";
import type { TableNodeData } from "../convert";

describe("autoInfer", () => {
  it("should infer relationships correctly based on _id columns", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "users_node",
        position: { x: 0, y: 0 },
        data: {
          title: "public.users",
          columns: [
            { column_name: "id", data_type: "integer", is_not_null: true, is_pk: true },
            { column_name: "name", data_type: "text", is_not_null: true, is_pk: false },
          ],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: "posts_node",
        position: { x: 100, y: 100 },
        data: {
          title: "public.posts",
          columns: [
            { column_name: "id", data_type: "integer", is_not_null: true, is_pk: true },
            { column_name: "user_id", data_type: "integer", is_not_null: true, is_pk: false },
          ],
          badges: { pk: true, fk: true },
        },
      },
      {
        id: "category_node",
        position: { x: 200, y: 200 },
        data: {
          title: "public.category",
          columns: [
            { column_name: "cat_code", data_type: "text", is_not_null: true, is_pk: true },
          ],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: "items_node",
        position: { x: 300, y: 300 },
        data: {
          title: "public.items",
          columns: [
            { column_name: "id", data_type: "integer", is_not_null: true, is_pk: true },
            { column_name: "category_id", data_type: "text", is_not_null: true, is_pk: false },
          ],
          badges: { pk: true, fk: true },
        },
      },
      {
        id: "tags_node",
        position: { x: 400, y: 400 },
        data: {
          title: "public.tags",
          columns: [
            { column_name: "id", data_type: "integer", is_not_null: true, is_pk: true },
            { column_name: "tag_id", data_type: "integer", is_not_null: true, is_pk: false },
          ],
          badges: { pk: true, fk: false },
        },
      }
    ];

    const edges = inferRelationships(nodes);

    expect(edges).toHaveLength(2);

    // users - posts (user_id -> users)
    const postEdge = edges.find(e => e.source === "posts_node");
    expect(postEdge).toBeDefined();
    expect(postEdge?.target).toBe("users_node");
    expect(postEdge?.data?.sourceColumns).toEqual(["user_id"]);
    expect(postEdge?.data?.targetColumns).toEqual(["id"]);

    // category - items (category_id -> category)
    // fallback to first pk column "cat_code" since there is no "id" column in category table
    const itemEdge = edges.find(e => e.source === "items_node");
    expect(itemEdge).toBeDefined();
    expect(itemEdge?.target).toBe("category_node");
    expect(itemEdge?.data?.sourceColumns).toEqual(["category_id"]);
    expect(itemEdge?.data?.targetColumns).toEqual(["cat_code"]);
  });

  it("should return empty array if no _id columns are found", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "table1",
        position: { x: 0, y: 0 },
        data: {
          title: "table1",
          columns: [{ column_name: "name", data_type: "text", is_not_null: false, is_pk: false }],
          badges: { pk: false, fk: false },
        },
      },
      {
        id: "table2",
        position: { x: 10, y: 10 },
        data: {
          title: "table2",
          columns: [{ column_name: "description", data_type: "text", is_not_null: false, is_pk: false }],
          badges: { pk: false, fk: false },
        },
      }
    ];

    const edges = inferRelationships(nodes);
    expect(edges).toHaveLength(0);
  });

  it("should not infer self relationships if it targets itself", () => {
     const nodes: Node<TableNodeData>[] = [
       {
         id: "employee",
         position: { x: 0, y: 0 },
         data: {
           title: "employee",
           columns: [
             { column_name: "id", data_type: "integer", is_not_null: true, is_pk: true },
             { column_name: "employee_id", data_type: "integer", is_not_null: false, is_pk: false }
           ],
           badges: { pk: true, fk: false },
         }
       }
     ];

     const edges = inferRelationships(nodes);
     expect(edges).toHaveLength(0);
  });

  it("should fallback to first column if no id or pk column exists", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "table_a",
        position: { x: 0, y: 0 },
        data: {
          title: "table_a",
          columns: [{ column_name: "random_col", data_type: "text", is_not_null: false, is_pk: false }],
          badges: { pk: false, fk: false },
        },
      },
      {
        id: "table_b",
        position: { x: 10, y: 10 },
        data: {
          title: "table_b",
          columns: [{ column_name: "table_a_id", data_type: "text", is_not_null: false, is_pk: false }],
          badges: { pk: false, fk: false },
        },
      }
    ];

    const edges = inferRelationships(nodes);
    expect(edges).toHaveLength(1);
    expect(edges[0].target).toBe("table_a");
    expect(edges[0].data?.targetColumns).toEqual(["random_col"]);
  });

  it("should not infer if target entity not found", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "table_b",
        position: { x: 10, y: 10 },
        data: {
          title: "table_b",
          columns: [{ column_name: "table_a_id", data_type: "text", is_not_null: false, is_pk: false }],
          badges: { pk: false, fk: false },
        },
      }
    ];

    const edges = inferRelationships(nodes);
    expect(edges).toHaveLength(0);
  });

  it("should correctly identify target table with suffix variations (s, es)", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "boxes_node",
        position: { x: 0, y: 0 },
        data: {
          title: "boxes",
          columns: [{ column_name: "id", data_type: "int", is_not_null: true, is_pk: true }],
          badges: { pk: true, fk: false },
        },
      },
      {
        id: "items_node",
        position: { x: 10, y: 10 },
        data: {
          title: "items",
          columns: [{ column_name: "box_id", data_type: "int", is_not_null: true, is_pk: false }],
          badges: { pk: false, fk: true },
        },
      }
    ];

    const edges = inferRelationships(nodes);
    expect(edges).toHaveLength(1);
    expect(edges[0].target).toBe("boxes_node");
  });
});
