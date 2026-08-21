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

  it("handles tables without optional searchable text", () => {
    const empty = tableNode("empty", { title: "", comment: "", columns: [] });
    expect(tableNodeMatchesSearch(empty, "missing")).toBe(false);
  });

  it("rebuilds cached text for immutable replacements of every searchable field", () => {
    const node1 = tableNode("n1", {
      title: "order",
      comment: "details",
      columns: [
        { column_name: "primary_key", data_type: "uuid", is_not_null: true, is_pk: true, column_comment: "identifier" }
      ]
    });

    // Baseline expectations
    expect(tableNodeMatchesSearch(node1, "order")).toBe(true);
    expect(tableNodeMatchesSearch(node1, "details")).toBe(true);
    expect(tableNodeMatchesSearch(node1, "primary_key")).toBe(true);
    expect(tableNodeMatchesSearch(node1, "uuid")).toBe(true);
    expect(tableNodeMatchesSearch(node1, "identifier")).toBe(true);
    expect(tableNodeMatchesSearch(node1, "customer")).toBe(false);

    // 1. Title change
    const titleChanged = { ...node1, data: { ...node1.data, title: "customer" } };
    expect(tableNodeMatchesSearch(titleChanged, "customer")).toBe(true);
    expect(tableNodeMatchesSearch(node1, "customer")).toBe(false); // original is unaffected
    expect(tableNodeMatchesSearch(titleChanged, "order")).toBe(false); // the old title should no longer match

    // 2. Comment change
    const commentChanged = { ...node1, data: { ...node1.data, comment: "billing" } };
    expect(tableNodeMatchesSearch(commentChanged, "billing")).toBe(true);
    expect(tableNodeMatchesSearch(commentChanged, "details")).toBe(false);

    // 3. Column name change
    const columnNameChanged = {
      ...node1,
      data: {
        ...node1.data,
        columns: [
          { column_name: "tracking", data_type: "uuid", is_not_null: true, is_pk: true, column_comment: "identifier" }
        ]
      }
    };
    expect(tableNodeMatchesSearch(columnNameChanged, "tracking")).toBe(true);
    expect(tableNodeMatchesSearch(columnNameChanged, "primary")).toBe(false);

    // 4. Column type change
    const dataTypeChanged = {
      ...node1,
      data: {
        ...node1.data,
        columns: [
          { column_name: "primary_key", data_type: "varchar", is_not_null: true, is_pk: true, column_comment: "identifier" }
        ]
      }
    };
    expect(tableNodeMatchesSearch(dataTypeChanged, "varchar")).toBe(true);
    expect(tableNodeMatchesSearch(dataTypeChanged, "uuid")).toBe(false);

    // 5. Column comment change
    const columnCommentChanged = {
      ...node1,
      data: {
        ...node1.data,
        columns: [
          { column_name: "primary_key", data_type: "uuid", is_not_null: true, is_pk: true, column_comment: "external" }
        ]
      }
    };
    expect(tableNodeMatchesSearch(columnCommentChanged, "external")).toBe(true);
    expect(tableNodeMatchesSearch(columnCommentChanged, "identifier")).toBe(false);
  });

  it("does not reread searchable fields for the same node-data identity", () => {
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
