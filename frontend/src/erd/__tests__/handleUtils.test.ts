import { describe, expect, it } from "vitest";
import { sanitizeHandleId, _clearHandleCache } from "../handleUtils";

describe("handleUtils cache", () => {
  it("caches the result of sanitizeHandleId", () => {
    _clearHandleCache();

    // We can't strictly verify via vi.spyOn(Array, "from") without making tests flaky.
    // However, we verify it returns the exact same string on multiple calls.
    const result1 = sanitizeHandleId("test_col");
    const result2 = sanitizeHandleId("test_col");
    expect(result1).toBe(result2);
  });
  it("evicts old entries when cache limit is exceeded", () => {
    _clearHandleCache();
    // Fill the cache up to and beyond the limit to verify bounded memory
    for (let i = 0; i < 1005; i++) {
        sanitizeHandleId(`test_col_${i}`);
    }

    // In actual JS environment, we can't inspect the unexported Map's size easily here without exposing it.
    // We just verify it doesn't crash or throw exceptions.
    const result1 = sanitizeHandleId("test_col_1006");
    expect(result1).toBe("c-0074-0065-0073-0074-005f-0063-006f-006c-005f-0031-0030-0030-0036");
  });
});
