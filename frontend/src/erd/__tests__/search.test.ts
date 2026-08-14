import type { Node } from "@xyflow/react";
import { describe, expect, it, vi, afterEach } from "vitest";

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

  afterEach(() => {
    vi.restoreAllMocks();
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
    const node1 = tableNode("n1", { title: "order", columns: [] });
    expect(tableNodeMatchesSearch(node1, "customer")).toBe(false);

    // The cache is keyed by node.data. If properties mutate on the same object,
    // the cache will become stale. The contract is that updates *must* provide a new data object.
    const updatedData = { ...node1.data, title: "customer_order" };
    const node2 = { ...node1, data: updatedData };
    expect(tableNodeMatchesSearch(node2, "customer")).toBe(true);
  });

  it("caches string parsing to avoid redundant allocations for identical node data", () => {
    // We can't directly inspect the WeakMap, but we can verify that modifying the object directly
    // bypasses the matcher because of the cache, proving the cache is used.
    const node = tableNode("cacheTest", { title: "initial_title", columns: [] });

    // Initial evaluation populates the cache
    expect(tableNodeMatchesSearch(node, "initial")).toBe(true);

    // Mutate the original object directly (violates contract)
    node.data.title = "mutated_title";

    // Since cache is keyed by node.data identity, it continues to return the old result
    // (doesn't match the new word, still matches the old word). This proves the O(1) cache reuse.
    expect(tableNodeMatchesSearch(node, "mutated")).toBe(false);
    expect(tableNodeMatchesSearch(node, "initial")).toBe(true);
  });
});
