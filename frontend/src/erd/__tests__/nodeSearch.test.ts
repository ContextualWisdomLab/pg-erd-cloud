import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";

import type { TableNodeData } from "../convert";
import { tableNodeMatchesSearch } from "../nodeSearch";

const node: Node<TableNodeData> = {
  id: "users",
  type: "tableNode",
  position: { x: 0, y: 0 },
  data: {
    title: "public.users",
    comment: "Application accounts",
    columns: [
      {
        column_name: "email_address",
        data_type: "varchar",
        is_not_null: true,
        is_pk: false,
        column_comment: "Primary login address",
      },
    ],
    badges: { pk: false, fk: false },
  },
};

describe("tableNodeMatchesSearch", () => {
  it("matches title, table comments, and column metadata without joined haystacks", () => {
    expect(tableNodeMatchesSearch(node, "users")).toBe(true);
    expect(tableNodeMatchesSearch(node, "accounts")).toBe(true);
    expect(tableNodeMatchesSearch(node, "email")).toBe(true);
    expect(tableNodeMatchesSearch(node, "varchar")).toBe(true);
    expect(tableNodeMatchesSearch(node, "login")).toBe(true);
  });

  it("returns false for empty or missing matches", () => {
    expect(tableNodeMatchesSearch(node, "")).toBe(false);
    expect(tableNodeMatchesSearch(node, "orders")).toBe(false);
  });
});
