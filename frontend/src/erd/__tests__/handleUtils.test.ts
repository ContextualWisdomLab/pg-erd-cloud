import { describe, expect, it, vi } from "vitest";
import { sanitizeHandleId, _handleCacheForTest } from "../handleUtils";

describe("handleUtils cache", () => {
  it("caches the result of sanitizeHandleId", () => {
    const spy = vi.spyOn(Array, "from");
    _handleCacheForTest.clear();
    const result1 = sanitizeHandleId("test_col");
    expect(spy).toHaveBeenCalled();
    spy.mockClear();

    const result2 = sanitizeHandleId("test_col");
    expect(result1).toBe(result2);
    expect(spy).not.toHaveBeenCalled(); // Cache hit, Array.from should not be called

    spy.mockRestore();
  });
  it("evicts old entries when cache limit is exceeded", () => {
    _handleCacheForTest.clear();
    for (let i = 0; i < 1005; i++) {
      sanitizeHandleId(`test_col_${i}`);
    }
    expect(_handleCacheForTest.size).toBeLessThanOrEqual(1000);
  });
});
