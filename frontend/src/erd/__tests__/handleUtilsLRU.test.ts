import { describe, it, expect, vi, afterEach } from 'vitest';
import { createSanitizeHandleIdCache, sanitizeHandleId } from '../handleUtils';

describe('sanitizeHandleId LRU cache behavior', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('bounds the cache size and evicts correctly using spy', () => {
    // We spy on Array.from to know if a cache miss occurred and recomputation happened.
    const spy = vi.spyOn(Array, 'from');

    // Create a very small cache for testing
    const cacheSize = 3;
    const testSanitize = createSanitizeHandleIdCache(cacheSize);

    // Add 3 items (3 cache misses)
    testSanitize('A');
    testSanitize('B');
    testSanitize('C');
    expect(spy).toHaveBeenCalledTimes(3);

    // Hit A so it becomes most recently used (no miss)
    testSanitize('A');
    expect(spy).toHaveBeenCalledTimes(3);

    // Add a 4th item, which should evict B (the least recently used)
    testSanitize('D');
    expect(spy).toHaveBeenCalledTimes(4); // Miss for D

    // Call C (should hit, not evict)
    testSanitize('C');
    expect(spy).toHaveBeenCalledTimes(4);

    // Call A (should hit, not evict)
    testSanitize('A');
    expect(spy).toHaveBeenCalledTimes(4);

    // If we call B again, it will be a cache miss because it was evicted.
    testSanitize('B');
    expect(spy).toHaveBeenCalledTimes(5); // This proves eviction occurred!
  });

  it('keeps identical results for different code points over 1000 items', () => {
     for (let i = 0; i < 1500; i++) {
        expect(sanitizeHandleId(`col_${i}`)).toBe(`c-0063-006f-006c-005f-${String(i).split('').map(c => c.charCodeAt(0).toString(16).padStart(4, '0')).join('-')}`);
     }
  });
});
