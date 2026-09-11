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

  it("matches table and column fields without building a joined haystack", () => {
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

  it("utilizes WeakMap cache to prevent redundant search execution", () => {
    const cache = new WeakMap<TableNodeData, boolean>();

    // First run populates the cache
    expect([...findSearchMatchedNodeIds([users, audit], "PUBLIC uuid", cache)]).toEqual(["users"]);
    expect(cache.has(users.data)).toBe(true);
    expect(cache.has(audit.data)).toBe(true);
    expect(cache.get(users.data)).toBe(true);
    expect(cache.get(audit.data)).toBe(false);

    // Modify the node properties outside the cache.
    // If the cache is used, it should still return the cached result.
    const modifiedUsers = { ...users, data: users.data };
    const modifiedAudit = { ...audit, data: audit.data };

    // This second call should hit the cache for both nodes
    expect([...findSearchMatchedNodeIds([modifiedUsers, modifiedAudit], "audit jsonb", cache)]).toEqual(["users"]);
  });
});
