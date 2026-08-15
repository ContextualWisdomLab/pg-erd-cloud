import type { Node } from "@xyflow/react";
import { describe, expect, it, beforeEach } from "vitest";

import type { TableNodeData } from "../convert";
import { findSearchMatchedNodeIds, tableNodeMatchesSearch, _getSearchCacheMisses, _resetSearchCacheMisses } from "../search";

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

describe("ERD node search", () => {
  beforeEach(() => {
    _resetSearchCacheMisses();
  });

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

  it("matches table and column fields by caching a unified searchable haystack string", () => {
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

  it("re-evaluates search results if node data identity changes (cache invalidation contract)", () => {
    const node1 = tableNode("n1", {
      title: "order",
      comment: "order details",
      columns: [
        { column_name: "id", data_type: "uuid", is_not_null: true, is_pk: true, column_comment: "order id" }
      ]
    });

    // Baseline expectations
    expect(tableNodeMatchesSearch(node1, "order")).toBe(true);
    expect(tableNodeMatchesSearch(node1, "customer")).toBe(false);

    // The cache is keyed by node.data. The contract requires immutable updates.
    // Verify each searchable field triggers a re-evaluation when part of a new data object reference.

    // 1. Title change
    let node2 = { ...node1, data: { ...node1.data, title: "customer_order" } };
    expect(tableNodeMatchesSearch(node2, "customer")).toBe(true);
    // Old node1 should remain unaffected
    expect(tableNodeMatchesSearch(node1, "customer")).toBe(false);

    // 2. Comment change
    let node3 = { ...node1, data: { ...node1.data, comment: "now includes billing" } };
    expect(tableNodeMatchesSearch(node3, "billing")).toBe(true);
    expect(tableNodeMatchesSearch(node3, "details")).toBe(false); // Overwritten comment

    // 3. Columns change (name, type, and comment)
    let node4 = {
      ...node1,
      data: {
        ...node1.data,
        columns: [
          { column_name: "tracking_code", data_type: "varchar", is_not_null: true, is_pk: true, column_comment: "shipping tracking" }
        ]
      }
    };
    expect(tableNodeMatchesSearch(node4, "tracking")).toBe(true);
    expect(tableNodeMatchesSearch(node4, "varchar")).toBe(true);
    expect(tableNodeMatchesSearch(node4, "shipping")).toBe(true);
    // Old column fields are no longer matched
    expect(tableNodeMatchesSearch(node4, "uuid")).toBe(false);
  });

  it("caches string parsing to avoid redundant allocations for identical node data", () => {
    const node = tableNode("perfTest", { title: "initial_title", columns: [] });
    const initialMisses = _getSearchCacheMisses();

    // Initial evaluation populates the cache
    expect(tableNodeMatchesSearch(node, "initial")).toBe(true);
    expect(_getSearchCacheMisses()).toBe(initialMisses + 1);

    // Evaluate multiple times simulating 60fps drag render ticks
    for(let i=0; i<100; i++) {
        expect(tableNodeMatchesSearch(node, "initial")).toBe(true);
    }

    // The cache miss counter should not have increased
    expect(_getSearchCacheMisses()).toBe(initialMisses + 1);
  });
});
