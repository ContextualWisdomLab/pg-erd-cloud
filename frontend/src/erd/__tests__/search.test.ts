import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import type { TableNodeData } from "../convert";
import { findSearchMatchedNodeIds, tableNodeMatchesSearch } from "../search";

function tableNode(
  id: string,
  data: Pick<TableNodeData, "title" | "columns"> &
    Partial<Pick<TableNodeData, "comment">>,
): Node<TableNodeData> {
  return {
    id,
    type: "tableNode",
    position: { x: 0, y: 0 },
    data: {
      badges: { pk: false, fk: false },
      comment: null,
      ...data,
    },
  };
}

function trackedTableNode(
  id: string,
  columnCount: number,
): { node: Node<TableNodeData>; searchableFieldReads: () => number } {
  let reads = 0;
  const target: TableNodeData = {
    title: `shared_marker_table_${id}`,
    comment: "tracked search cache fixture",
    badges: { pk: false, fk: false },
    columns: Array.from({ length: columnCount }, (_, index) => ({
      column_name: `column_${index}`,
      data_type: "text",
      is_not_null: true,
      is_pk: index === 0,
      column_comment: `column comment ${index}`,
    })),
  };
  const data = new Proxy(target, {
    get(currentTarget, property, receiver) {
      if (property === "title" || property === "comment" || property === "columns") {
        reads += 1;
      }
      return Reflect.get(currentTarget, property, receiver);
    },
  });

  return {
    node: {
      id,
      type: "tableNode",
      position: { x: 0, y: 0 },
      data,
    },
    searchableFieldReads: () => reads,
  };
}

describe("ERD node search", () => {
  const users = tableNode("users", {
    title: "public.users",
    comment: "Customer profile records",
    columns: [
      {
        column_name: "id",
        data_type: "uuid",
        is_not_null: true,
        is_pk: true,
      },
      {
        column_name: "email_address",
        data_type: "text",
        is_not_null: true,
        is_pk: false,
        column_comment: "Login email",
      },
    ],
  });

  const audit = tableNode("audit", {
    title: "ops.audit_log",
    columns: [
      {
        column_name: "payload",
        data_type: "jsonb",
        is_not_null: false,
        is_pk: false,
      },
    ],
  });

  it("returns no matches for an empty search", () => {
    expect([...findSearchMatchedNodeIds([users, audit], "   ")]).toEqual([]);
  });

  it("matches table and column fields through one searchable text value", () => {
    expect([...findSearchMatchedNodeIds([users, audit], "PUBLIC uuid")]).toEqual([
      "users",
    ]);
    expect([...findSearchMatchedNodeIds([users, audit], "customer email")]).toEqual([
      "users",
    ]);
    expect([...findSearchMatchedNodeIds([users, audit], "audit jsonb")]).toEqual([
      "audit",
    ]);
  });

  it("requires every search term to appear somewhere on the same node", () => {
    expect(tableNodeMatchesSearch(users, "users jsonb")).toBe(false);
    expect(tableNodeMatchesSearch(audit, "audit missing")).toBe(false);
  });

  it("rebuilds cached text for immutable replacements of every searchable field", () => {
    const original = tableNode("order", {
      title: "order_title",
      comment: "order_details",
      columns: [
        {
          column_name: "order_id",
          data_type: "uuid",
          is_not_null: true,
          is_pk: true,
          column_comment: "order_identifier",
        },
      ],
    });
    expect(tableNodeMatchesSearch(original, "order_title order_details order_id uuid order_identifier")).toBe(true);

    const titleChanged = {
      ...original,
      data: { ...original.data, title: "customer_title" },
    };
    expect(tableNodeMatchesSearch(titleChanged, "customer_title")).toBe(true);
    expect(tableNodeMatchesSearch(titleChanged, "order_title")).toBe(false);

    const commentChanged = {
      ...original,
      data: { ...original.data, comment: "billing_details" },
    };
    expect(tableNodeMatchesSearch(commentChanged, "billing_details")).toBe(true);
    expect(tableNodeMatchesSearch(commentChanged, "order_details")).toBe(false);

    const columnNameChanged = {
      ...original,
      data: {
        ...original.data,
        columns: [{ ...original.data.columns[0]!, column_name: "tracking_code" }],
      },
    };
    expect(tableNodeMatchesSearch(columnNameChanged, "tracking_code")).toBe(true);
    expect(tableNodeMatchesSearch(columnNameChanged, "order_id")).toBe(false);

    const dataTypeChanged = {
      ...original,
      data: {
        ...original.data,
        columns: [{ ...original.data.columns[0]!, data_type: "varchar" }],
      },
    };
    expect(tableNodeMatchesSearch(dataTypeChanged, "varchar")).toBe(true);
    expect(tableNodeMatchesSearch(dataTypeChanged, "uuid")).toBe(false);

    const columnCommentChanged = {
      ...original,
      data: {
        ...original.data,
        columns: [
          { ...original.data.columns[0]!, column_comment: "shipping_reference" },
        ],
      },
    };
    expect(tableNodeMatchesSearch(columnCommentChanged, "shipping_reference")).toBe(true);
    expect(tableNodeMatchesSearch(columnCommentChanged, "order_identifier")).toBe(false);
    expect(tableNodeMatchesSearch(original, "customer_title billing_details tracking_code varchar shipping_reference")).toBe(false);
  });

  it("does not reread searchable fields for the same node-data identity", () => {
    const tracked = trackedTableNode("identity", 20);

    expect(tableNodeMatchesSearch(tracked.node, "shared_marker column_19")).toBe(true);
    const readsAfterBuild = tracked.searchableFieldReads();
    expect(readsAfterBuild).toBeGreaterThan(0);

    for (let index = 0; index < 100; index += 1) {
      expect(tableNodeMatchesSearch(tracked.node, "shared_marker column_19")).toBe(true);
    }
    expect(tracked.searchableFieldReads()).toBe(readsAfterBuild);

    const replacement = trackedTableNode("identity", 20);
    expect(tableNodeMatchesSearch(replacement.node, "shared_marker column_19")).toBe(true);
    expect(replacement.searchableFieldReads()).toBeGreaterThan(0);
    expect(tracked.searchableFieldReads()).toBe(readsAfterBuild);
  });

  it("reuses cached text across 1,000 fixed-shape nodes", () => {
    const trackedNodes = Array.from({ length: 1_000 }, (_, index) =>
      trackedTableNode(`node_${index}`, 20),
    );
    const nodes = trackedNodes.map(({ node }) => node);

    expect(findSearchMatchedNodeIds(nodes, "shared_marker column_19").size).toBe(1_000);
    const readsAfterBuild = trackedNodes.reduce(
      (total, tracked) => total + tracked.searchableFieldReads(),
      0,
    );
    expect(readsAfterBuild).toBeGreaterThan(0);

    expect(findSearchMatchedNodeIds(nodes, "shared_marker column_19").size).toBe(1_000);
    expect(
      trackedNodes.reduce(
        (total, tracked) => total + tracked.searchableFieldReads(),
        0,
      ),
    ).toBe(readsAfterBuild);
  });
});
