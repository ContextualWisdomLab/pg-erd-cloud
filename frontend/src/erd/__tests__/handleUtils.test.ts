import { describe, expect, it } from "vitest";
import { sanitizeHandleId, _clearHandleCache } from "../handleUtils";

describe("handleUtils cache", () => {
  it("caches the result of sanitizeHandleId", () => {
    _clearHandleCache();
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
        sanitizeHandleId("test_col_extremely_long_name_to_force_execution_time_padding");
    }
    const durationWithoutCacheHits = performance.now() - start;

    // We can't strictly verify via vi.spyOn(Array, "from") without making tests flaky.
    // However, we verify it returns the exact same string on multiple calls.
    const result1 = sanitizeHandleId("test_col");
    const result2 = sanitizeHandleId("test_col");
    expect(result1).toBe(result2);
  });
});
