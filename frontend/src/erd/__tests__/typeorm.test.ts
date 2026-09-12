import { describe, it, expect } from "vitest";
import { exportTypeOrm } from "../typeorm";
import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "../convert";
import { sourceColumnHandleId, targetColumnHandleId } from "../handleUtils";

describe("exportTypeOrm", () => {
  it("should return empty string comment when no nodes are provided", () => {
    expect(exportTypeOrm([], [])).toBe("// No tables to export\n");
  });

  it("should export nodes and edges to TypeORM entities, preventing collision and using proper identifiers", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "1",
        type: "tableNode",
        position: { x: 0, y: 0 },
        data: {
          title: "public.users",
          columns: [
            { column_name: "id", data_type: "serial", is_pk: true, is_not_null: true },
            { column_name: "name", data_type: "varchar", is_pk: false, is_not_null: true },
            { column_name: "is_active", data_type: "bool", is_pk: false, is_not_null: false },
            { column_name: "created_at", data_type: "timestamp", is_pk: false, is_not_null: false }
          ],
          badges: { pk: true, fk: false }
        }
      },
      {
        id: "2",
        type: "tableNode",
        position: { x: 100, y: 100 },
        data: {
          title: "public.posts",
          columns: [
            { column_name: "id", data_type: "uuid", is_pk: true, is_not_null: true },
            { column_name: "user_id", data_type: "int", is_pk: false, is_not_null: true },
            { column_name: "amount", data_type: "numeric", is_pk: false, is_not_null: true }
          ],
          badges: { pk: true, fk: true }
        }
      },
      {
        id: "3",
        type: "tableNode",
        position: { x: 200, y: 200 },
        data: {
          title: "standalone",
          columns: [
            { column_name: "code", data_type: "varchar", is_pk: true, is_not_null: true },
          ],
          badges: { pk: true, fk: false }
        }
      },
      {
        id: "4",
        type: "tableNode",
        position: { x: 300, y: 300 },
        data: {
          title: "public.users", // duplicate base name
          columns: [
            { column_name: "id", data_type: "int", is_pk: true, is_not_null: true },
          ],
          badges: { pk: true, fk: false }
        }
      }
    ];

    const edges: Edge[] = [
      {
        id: "e1",
        source: "2",
        target: "1",
        sourceHandle: sourceColumnHandleId("user_id"),
        targetHandle: targetColumnHandleId("id")
      }
    ];

    const output = exportTypeOrm(nodes, edges);
    expect(output).toContain("import { Entity, PrimaryGeneratedColumn, Column");
    expect(output).toContain("@Entity({ name: \"users\", schema: \"public\" })");
    expect(output).toContain("export class Users {");
    expect(output).toContain("@PrimaryGeneratedColumn({ name: \"id\" })");
    expect(output).toContain("id: number;");
    expect(output).toContain("is_active?: boolean;");
    expect(output).toContain("created_at?: Date;");
    expect(output).toContain("@OneToMany(() => Posts, (e) => e.posts_user_id)");

    expect(output).toContain("@Entity({ name: \"posts\", schema: \"public\" })");
    expect(output).toContain("export class Posts {");
    // UUID should be PrimaryColumn with type, NOT PrimaryGeneratedColumn
    expect(output).toContain("@PrimaryColumn({ name: \"id\", type: \"uuid\" })");
    expect(output).toContain("id: string;");
    expect(output).toContain("amount: number;");
    expect(output).toContain("@ManyToOne(() => Users)");
    expect(output).toContain("@JoinColumn({ name: \"user_id\", referencedColumnName: \"id\" })");

    expect(output).toContain("@PrimaryColumn({ name: \"code\", type: \"varchar\" })");
    expect(output).toContain("code: string;");

    // Collision checking
    expect(output).toContain("export class Users_1 {");
  });

  it("should handle composite foreign keys using sourceColumns array", () => {
      const nodes: Node<TableNodeData>[] = [
      {
        id: "1",
        type: "tableNode",
        position: { x: 0, y: 0 },
        data: {
          title: "parent",
          columns: [
            { column_name: "k1", data_type: "int", is_pk: true, is_not_null: true },
            { column_name: "k2", data_type: "int", is_pk: true, is_not_null: true }
          ],
          badges: { pk: true, fk: false }
        }
      },
      {
        id: "2",
        type: "tableNode",
        position: { x: 10, y: 10 },
        data: {
          title: "child",
          columns: [
            { column_name: "id", data_type: "int", is_pk: true, is_not_null: true },
            { column_name: "fk1", data_type: "int", is_pk: false, is_not_null: true },
            { column_name: "fk2", data_type: "int", is_pk: false, is_not_null: true }
          ],
          badges: { pk: true, fk: true }
        }
      }
    ];

    const edges: Edge[] = [
      {
        id: "e1",
        source: "2",
        target: "1",
        data: {
          sourceColumns: ["fk1", "fk2"],
          targetColumns: ["k1", "k2"]
        }
      }
    ];

    const output = exportTypeOrm(nodes, edges);
    expect(output).toContain("@JoinColumn([{ name: \"fk1\", referencedColumnName: \"k1\" }, { name: \"fk2\", referencedColumnName: \"k2\" }])");
    expect(output).toContain("parent_fk1_fk2?: Parent;");
  });

  it("should sanitize names and handle edges without handles", () => {
    const nodes: Node<TableNodeData>[] = [
      {
        id: "1",
        type: "tableNode",
        position: { x: 0, y: 0 },
        data: {
          title: "1invalid",
          columns: [
            { column_name: "1id", data_type: "integer", is_pk: true, is_not_null: true }
          ],
          badges: { pk: true, fk: false }
        }
      },
      {
        id: "2",
        type: "tableNode",
        position: { x: 10, y: 10 },
        data: {
          title: "valid",
          columns: [
            { column_name: "id", data_type: "integer", is_pk: true, is_not_null: true }
          ],
          badges: { pk: true, fk: true }
        }
      }
    ];

    const edges: Edge[] = [
      {
        id: "e1",
        source: "2",
        target: "1",
        // Missing handles to cover fkNodesWithoutHandles logic
      }
    ];

    const output = exportTypeOrm(nodes, edges);
    expect(output).toContain("export class Entity_1invalid {");
    expect(output).toContain("prop_1id: number;");
  });

  it("should handle edges targeting non-existent nodes", () => {
      const nodes: Node<TableNodeData>[] = [
      {
        id: "2",
        type: "tableNode",
        position: { x: 10, y: 10 },
        data: {
          title: "valid",
          columns: [
            { column_name: "id", data_type: "integer", is_pk: true, is_not_null: true }
          ],
          badges: { pk: true, fk: true }
        }
      }
    ];

    const edges: Edge[] = [
      {
        id: "e1",
        source: "2",
        target: "999", // non-existent
      }
    ];

    const output = exportTypeOrm(nodes, edges);
    expect(output).toContain("export class Valid {");
  });
});
