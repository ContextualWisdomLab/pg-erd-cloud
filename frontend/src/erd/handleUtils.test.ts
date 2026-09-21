import { describe, it, expect, vi } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, createSanitizeHandleIdCache } from './handleUtils';

describe('handleUtils', () => {
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

    it('should use LRU cache effectively and respect maxCacheSize bounds', () => {
      const arrayFromSpy = vi.spyOn(Array, 'from');
      const customSanitize = createSanitizeHandleIdCache(2);

      arrayFromSpy.mockClear();

      customSanitize('a');
      expect(arrayFromSpy).toHaveBeenCalledTimes(1);

      customSanitize('a');
      expect(arrayFromSpy).toHaveBeenCalledTimes(1);

      customSanitize('b');
      expect(arrayFromSpy).toHaveBeenCalledTimes(2);

      customSanitize('c');
      expect(arrayFromSpy).toHaveBeenCalledTimes(3);
      // cache: [b, c]

      customSanitize('a');
      expect(arrayFromSpy).toHaveBeenCalledTimes(4);
      // cache: [c, a]

      customSanitize('c');
      expect(arrayFromSpy).toHaveBeenCalledTimes(4);
      // cache: [a, c] (c re-inserted)

      customSanitize('d');
      expect(arrayFromSpy).toHaveBeenCalledTimes(5);
      // cache: [c, d]

      customSanitize('b');
      expect(arrayFromSpy).toHaveBeenCalledTimes(6);
      // cache: [d, b]

      customSanitize('c');
      expect(arrayFromSpy).toHaveBeenCalledTimes(7);
      // cache: [b, c]

      arrayFromSpy.mockRestore();
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
