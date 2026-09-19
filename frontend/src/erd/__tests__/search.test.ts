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


  it("uses the cached haystack for the same node data reference", () => {
    // Missing title and comment to cover lines 15, 19-20
    const minimalNode = tableNode("minimal", {
      title: "",
      columns: [
        {
          column_name: "test_col",
          data_type: "",
          is_not_null: false,
          is_pk: false,
        }
      ]
    });

    // Test branch coverage where data.title and data_type is falsy, but others are not
    const mixedNode = tableNode("mixed", {
        title: "",
        comment: "Comment",
        columns: [
            {
                column_name: "",
                data_type: "type",
                column_comment: "ccomment",
                is_not_null: false,
                is_pk: false
            }
        ]
    });

    // Both searches should use the exact same cached string internally
    expect([...findSearchMatchedNodeIds([minimalNode], "test_col")]).toEqual(["minimal"]);
    expect([...findSearchMatchedNodeIds([minimalNode], "test_col")]).toEqual(["minimal"]);
    expect([...findSearchMatchedNodeIds([mixedNode], "type")]).toEqual(["mixed"]);
  });
});
