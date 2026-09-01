import { describe, expect, it } from "vitest";

import { snapshotToGraph } from "./convert";

type SnapshotInput = Parameters<typeof snapshotToGraph>[0];

describe("snapshotToGraph relationship-aware layout", () => {
  it("places referenced tables before dependent tables on initial conversion", () => {
    const snapshot: SnapshotInput = {
      relations: [
        {
          relation_oid: 2,
          relation_kind: "r",
          schema_name: "public",
          relation_name: "orders",
        },
        {
          relation_oid: 1,
          relation_kind: "r",
          schema_name: "public",
          relation_name: "customers",
        },
      ],
      columns: [
        {
          relation_oid: 1,
          column_name: "id",
          data_type: "bigint",
          is_not_null: true,
        },
        {
          relation_oid: 2,
          column_name: "customer_id",
          data_type: "bigint",
          is_not_null: true,
        },
      ],
      constraints: [],
      fk_edges: [
        {
          fk_constraint_oid: 100,
          fk_constraint_name: "orders_customer_fk",
          child_relation_oid: 2,
          parent_relation_oid: 1,
          child_column_name: "customer_id",
          parent_column_name: "id",
          column_ordinal: 1,
        },
      ],
    };

    const graph = snapshotToGraph(snapshot);
    const parent = graph.nodes.find((node) => node.id === "1");
    const child = graph.nodes.find((node) => node.id === "2");

    expect(parent).toBeDefined();
    expect(child).toBeDefined();
    expect(parent!.position.x).toBeLessThan(child!.position.x);
    expect(graph.edges).toHaveLength(1);
    expect(graph.edges[0]).toMatchObject({ source: "2", target: "1" });
  });
});
