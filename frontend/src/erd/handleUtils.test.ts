import { describe, it, expect, vi } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, createHandleIdCache } from './handleUtils';

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

  describe('createHandleIdCache', () => {
    it('should memoize handle ids and enforce max size LRU policy', () => {
      const cacheSanitize = createHandleIdCache(2);
      const arrayFromSpy = vi.spyOn(Array, 'from');

      // Misses
      cacheSanitize('a');
      cacheSanitize('b');
      expect(arrayFromSpy).toHaveBeenCalledTimes(2);

      // Hits
      cacheSanitize('a');
      cacheSanitize('b');
      expect(arrayFromSpy).toHaveBeenCalledTimes(2);

      // Access 'a' to make it most recently used
      cacheSanitize('a');
      expect(arrayFromSpy).toHaveBeenCalledTimes(2);

      // Insert 'c' (miss), cache is now ['a', 'c'], 'b' is evicted
      cacheSanitize('c');
      expect(arrayFromSpy).toHaveBeenCalledTimes(3);

      // Access 'a' (hit because it was recently used before 'c' and therefore not evicted)
      cacheSanitize('a');
      expect(arrayFromSpy).toHaveBeenCalledTimes(3);

      // Access 'b' (miss because it was evicted)
      cacheSanitize('b');
      expect(arrayFromSpy).toHaveBeenCalledTimes(4);

      arrayFromSpy.mockRestore();
    });
  });
});
