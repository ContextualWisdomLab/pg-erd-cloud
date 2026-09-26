import { describe, it, expect, vi } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, createSanitizeHandleCache } from './handleUtils';

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

  describe('Cache', () => {
    it('should return cached result on subsequent calls', () => {
      const boundedCache = createSanitizeHandleCache();

      const spy = vi.spyOn(String.prototype, 'codePointAt');

      boundedCache('col1');
      expect(spy).toHaveBeenCalled();

      spy.mockClear();
      boundedCache('col1');
      expect(spy).not.toHaveBeenCalled(); // Cache hit

      spy.mockRestore();
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
