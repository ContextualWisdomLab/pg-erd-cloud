import { describe, expect, it } from "vitest";

import {
  toPlainText,
  snapshotDetailFromResponse,
  SnapshotDetailResponse,
} from "./types";

describe("toPlainText", () => {
  it("escapes html-sensitive characters and strips control characters", () => {
    expect(toPlainText('<script>alert("x")</script>\u0000')).toBe(
      "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;",
    );
  });

  it("returns null for non-string or empty values", () => {
    expect(toPlainText(null)).toBeNull();
    expect(toPlainText("")).toBeNull();
  });
});

describe("snapshotDetailFromResponse", () => {
  const baseResponse: Omit<SnapshotDetailResponse, "error_message"> = {
    schema_snapshot_uuid: "123-456",
    status: "COMPLETED",
    schema_filter: null,
    snapshot_json: null,
  };

  it("maps a response object to a domain model, properly applying toPlainText to error_message", () => {
    const response: SnapshotDetailResponse = {
      ...baseResponse,
      error_message: '<script>alert("x")</script>',
    };

    const detail = snapshotDetailFromResponse(response);

    expect(detail).toEqual({
      ...baseResponse,
      error_message: "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;",
    });
  });

  it("handles null error_message appropriately", () => {
    const response: SnapshotDetailResponse = {
      ...baseResponse,
      error_message: null,
    };

    const detail = snapshotDetailFromResponse(response);

    expect(detail).toEqual({
      ...baseResponse,
      error_message: null,
    });
  });
});
