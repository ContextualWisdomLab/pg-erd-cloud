import { describe, it, expect, vi, afterEach } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils';

describe('handleUtils', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('sanitizeHandleId', () => {
    it('should memoize calculations and limit cache size', () => {
      const spy = vi.spyOn(Array, 'from');
      // 1. Initial call computes
      sanitizeHandleId('test1');
      expect(spy).toHaveBeenCalledTimes(1);

      // 2. Second call should hit cache (no additional Array.from call)
      sanitizeHandleId('test1');
      expect(spy).toHaveBeenCalledTimes(1);

      // 3. Force cache eviction (max size 1000)
      for (let i = 0; i < 1001; i++) {
        sanitizeHandleId(`evict-${i}`);
      }

      // 4. 'test1' should be evicted, so it computes again
      spy.mockClear();
      sanitizeHandleId('test1');
      expect(spy).toHaveBeenCalledTimes(1);
    });

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
