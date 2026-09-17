import { describe, it, expect, vi, afterEach } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, createHandleIdSanitizer } from './handleUtils';

describe('handleUtils', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('sanitizeHandleId', () => {
    it('should encode a simple ascii string', () => {
      expect(sanitizeHandleId('id')).toBe('c-0069-0064');
    });

    it('should handle empty string', () => {
      expect(sanitizeHandleId('')).toBe('c-empty');
    });

    it('should handle special characters', () => {
      expect(sanitizeHandleId('user_id')).toBe('c-0075-0073-0065-0072-005f-0069-0064');
    });

    it('should handle unicode characters', () => {
      expect(sanitizeHandleId('id_가')).toBe('c-0069-0064-005f-ac00');
    });

    it('should handle emojis', () => {
      expect(sanitizeHandleId('id_🚀')).toBe('c-0069-0064-005f-1f680');
    });
  });

  describe('cache eviction', () => {
    it('should evict the oldest item when exceeding maxSize', () => {
      const sanitizer = createHandleIdSanitizer(2);
      const spy = vi.spyOn(Array, 'from');

      sanitizer('a'); // cache: 'a'
      sanitizer('b'); // cache: 'a', 'b'
      expect(spy).toHaveBeenCalledTimes(2);

      sanitizer('a'); // cache: 'b', 'a' (LRU update)
      expect(spy).toHaveBeenCalledTimes(2); // cached

      sanitizer('c'); // cache: 'a', 'c' (evicts 'b')
      expect(spy).toHaveBeenCalledTimes(3);

      sanitizer('b'); // 'b' was evicted, must recompute
      expect(spy).toHaveBeenCalledTimes(4); // recomputed
    });
  });

  describe('sourceColumnHandleId', () => {
    it('should prepend src- to sanitized id', () => {
      expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064');
    });
  });

  describe('targetColumnHandleId', () => {
    it('should prepend tgt- to sanitized id', () => {
      expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064');
    });
  });
});
