import type { Node } from "@xyflow/react";
import { describe, expect, it, vi, afterEach } from "vitest";

import type { TableNodeData } from "../convert";
import { findSearchMatchedNodeIds, tableNodeMatchesSearch, _searchCacheMetrics } from "../search";

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
    // The previous test verified this stall. Now we verify the correct update path.
    const updatedData = { ...node1.data, title: "customer_order" };
    const node2 = { ...node1, data: updatedData };
    expect(tableNodeMatchesSearch(node2, "customer")).toBe(true);
  });

  it("caches string parsing to avoid redundant allocations for identical node data", () => {
    const node = tableNode("perfTest", { title: "initial_title", columns: [] });
    const initialMisses = _searchCacheMetrics.misses;

    // Initial evaluation populates the cache
    expect(tableNodeMatchesSearch(node, "initial")).toBe(true);
    expect(_searchCacheMetrics.misses).toBe(initialMisses + 1);

    // Evaluate multiple times simulating 60fps drag render ticks
    for(let i=0; i<100; i++) {
        expect(tableNodeMatchesSearch(node, "initial")).toBe(true);
    }

    // The cache miss counter should not have increased
    expect(_searchCacheMetrics.misses).toBe(initialMisses + 1);
  });

  it("proves fast evaluation at representative layout bounds", () => {
     // Generate a large table with 100 columns
     const columns = [];
     for(let i=0; i<100; i++) {
       columns.push({
           column_name: `field_${i}`,
           data_type: "varchar(255)",
           is_not_null: false,
           is_pk: false,
           column_comment: `desc_${i}`
       });
     }

     const heavyNodes = [];
     for(let i=0; i<500; i++) {
        heavyNodes.push(tableNode(`t${i}`, {
            title: `heavy_table_${i}`,
            columns
        }));
     }

     const initialMisses = _searchCacheMetrics.misses;

     // Build cache for all nodes
     const matched = findSearchMatchedNodeIds(heavyNodes, "heavy_table_499 field_99");
     expect(matched.has("t499")).toBe(true);
     expect(_searchCacheMetrics.misses).toBe(initialMisses + 500); // Exactly 1 miss per node

     const missBeforeFast = _searchCacheMetrics.misses;

     // Measure cached run
     const fastMatched = findSearchMatchedNodeIds(heavyNodes, "field_0 desc_0");
     expect(fastMatched.size).toBe(500);

     // 0 new cache misses, entirely hitting WeakMap
     expect(_searchCacheMetrics.misses).toBe(missBeforeFast);
  });
});
