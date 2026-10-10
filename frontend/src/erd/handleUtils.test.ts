import { describe, it, expect, vi } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, createSanitizeHandleId } from './handleUtils';

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

  describe('createSanitizeHandleId cache eviction', () => {
    it('should evict the oldest entry when exceeding maxSize', () => {
      const cachedSanitize = createSanitizeHandleId(2);

      // Fill cache to max
      cachedSanitize('id1');
      cachedSanitize('id2');

      // Access id1 to update its insertion order (making id2 the oldest)
      cachedSanitize('id1');

      // Add id3, which should exceed maxSize and evict id2
      cachedSanitize('id3');

      const arrayFromSpy = vi.spyOn(Array, 'from');

      // id1 should be in cache (no computation)
      cachedSanitize('id1');
      expect(arrayFromSpy).not.toHaveBeenCalled();

      // id3 should be in cache (no computation)
      cachedSanitize('id3');
      expect(arrayFromSpy).not.toHaveBeenCalled();

      // id2 should have been evicted, requiring computation
      cachedSanitize('id2');
      expect(arrayFromSpy).toHaveBeenCalled();

      arrayFromSpy.mockRestore();
    });
  });
});
