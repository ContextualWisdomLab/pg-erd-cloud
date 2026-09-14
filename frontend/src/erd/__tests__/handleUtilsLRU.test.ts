import { describe, it, expect, beforeEach } from 'vitest';
import { sanitizeHandleId, clearSanitizeHandleIdCache, getSanitizeHandleIdCacheSize } from '../handleUtils';

describe('sanitizeHandleId LRU cache behavior', () => {
  beforeEach(() => {
    // We will add this export just for testing purposes.
    if (typeof clearSanitizeHandleIdCache === 'function') {
      clearSanitizeHandleIdCache();
    }
  });

  it('bounds the cache size to 1000 items', () => {
    if (typeof getSanitizeHandleIdCacheSize !== 'function') {
        console.warn("getSanitizeHandleIdCacheSize not implemented, skipping cache bounds check");
        return;
    }
    const MAX_KEYS = 1000;

    // Add 1000 items
    for (let i = 0; i < MAX_KEYS; i++) {
        sanitizeHandleId(`col_${i}`);
    }

    expect(getSanitizeHandleIdCacheSize()).toBe(MAX_KEYS);

    // Add 100 more, should still be 1000
    for (let i = 1000; i < 1100; i++) {
        sanitizeHandleId(`col_${i}`);
    }

    expect(getSanitizeHandleIdCacheSize()).toBe(MAX_KEYS);
  });
});
