import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import type { TableNodeData } from "../convert";
import { findSearchMatchedNodeIds, tableNodeMatchesSearch, getSearchTerms } from "../search";

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
    expect(tableNodeMatchesSearch(users, "   ")).toBe(false);
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

  it("extracts unique non-empty search terms", () => {
    expect(getSearchTerms("")).toEqual([]);
    expect(getSearchTerms("   ")).toEqual([]);
    expect(getSearchTerms("a a a")).toEqual(["a"]);
    expect(getSearchTerms(" a  b   ")).toEqual(["a", "b"]);
  });

  it("handles null search terms gracefully", () => {
    expect(tableNodeMatchesSearch(tableNode("nulls", { title: null as any, columns: [] }), "users jsonb")).toBe(false);
    expect(tableNodeMatchesSearch(tableNode("nulls2", { title: "a", comment: undefined, columns: [] }), "users jsonb")).toBe(false);
    expect(tableNodeMatchesSearch(tableNode("nulls3", { title: "a", comment: "b", columns: [{ column_name: null as any, data_type: "text", is_not_null: false, is_pk: false }] }), "users")).toBe(false);
    expect(tableNodeMatchesSearch(tableNode("nulls4", { title: "a", comment: "b", columns: [{ column_name: "c", data_type: null as any, is_not_null: false, is_pk: false }] }), "users")).toBe(false);
    expect(tableNodeMatchesSearch(tableNode("nulls5", { title: "", comment: "b", columns: [] }), "users")).toBe(false);
    expect(tableNodeMatchesSearch(tableNode("nulls6", { title: "a", comment: "b", columns: [{ column_name: "", data_type: "text", is_not_null: false, is_pk: false }] }), "users")).toBe(false);

    // Explicitly test the return true branching for columns
    expect(tableNodeMatchesSearch(tableNode("nulls7", { title: "a", comment: "b", columns: [{ column_name: "c", data_type: "text", column_comment: "login email", is_not_null: false, is_pk: false }] }), "login")).toBe(true);
    expect(tableNodeMatchesSearch(tableNode("nulls8", { title: "a", comment: "b", columns: [{ column_name: "c", data_type: "text", is_not_null: false, is_pk: false }] }), "text")).toBe(true);
  });

  it("matches search term edge cases", () => {
    // Tests that getSearchTerms internal branching covers when splitting empty string gives [""] which gets filtered out
    expect(findSearchMatchedNodeIds([users], "    ").size).toBe(0);
    // Duplicate search terms edge case
    expect(getSearchTerms("term term")).toEqual(["term"]);

    // Test early break coverage in tableNodeMatchesSearch for multiple terms where first fails
    expect(tableNodeMatchesSearch(users, "missingterm public")).toBe(false);
    expect(tableNodeMatchesSearch(users, "public missingterm")).toBe(false);

    // Test early return coverage in tableNodeMatchesSearch for matching items
    expect(tableNodeMatchesSearch(users, "public uuid")).toBe(true);

    // Test findSearchMatchedNodeIds branch where terms fail
    expect(findSearchMatchedNodeIds([users], "missingterm").size).toBe(0);
    expect(findSearchMatchedNodeIds([users], "public missingterm").size).toBe(0);

    // Test finding multiple nodes with matching terms that partially match some fields but all match a node
    expect(findSearchMatchedNodeIds([users, audit], "public").size).toBe(1);

    // Test matching where field Includes finds a match based on a term exactly
    expect(tableNodeMatchesSearch(tableNode("matchEmptyStr", { title: "users", columns: [] }), "users")).toBe(true);
  });
});
