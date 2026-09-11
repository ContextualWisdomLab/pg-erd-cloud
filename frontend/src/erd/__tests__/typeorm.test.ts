import { describe, it, expect } from "vitest";
import { exportTypeOrm } from "../typeorm";
import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "../convert";

describe("exportTypeOrm", () => {
  it("should return empty string comment when no nodes are provided", () => {
    expect(exportTypeOrm([], [])).toBe("// No tables to export\n");
  });

  it("should export nodes and edges to TypeORM entities", () => {
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
      }
    ];

    const edges: Edge[] = [
      {
        id: "e1",
        source: "2",
        target: "1",
        sourceHandle: "src-user_id",
        targetHandle: "tgt-id"
      }
    ];

    const output = exportTypeOrm(nodes, edges);
    expect(output).toContain("import { Entity, PrimaryGeneratedColumn, Column");
    expect(output).toContain("@Entity({ name: \"users\", schema: \"public\" })");
    expect(output).toContain("export class Public_users {");
    expect(output).toContain("@PrimaryGeneratedColumn()");
    expect(output).toContain("id: number;");
    expect(output).toContain("is_active?: boolean;");
    expect(output).toContain("created_at?: Date;");
    expect(output).toContain("@OneToMany(() => Public_posts, (e) => e.public_posts_user_id)");

    expect(output).toContain("@Entity({ name: \"posts\", schema: \"public\" })");
    expect(output).toContain("export class Public_posts {");
    expect(output).toContain("@PrimaryGeneratedColumn(\"uuid\")");
    expect(output).toContain("id: string;");
    expect(output).toContain("amount: number;");
    expect(output).toContain("@ManyToOne(() => Public_users)");
    expect(output).toContain("@JoinColumn({ name: \"user_id\", referencedColumnName: \"id\" })");

    expect(output).toContain("@PrimaryColumn()");
    expect(output).toContain("code: string;");
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
