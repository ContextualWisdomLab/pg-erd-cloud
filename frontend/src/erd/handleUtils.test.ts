import { describe, it, expect, vi, afterEach } from 'vitest';
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
  });

  describe('createSanitizeHandleIdCache', () => {
    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('should cache results and use LRU eviction policy', () => {
      const spy = vi.spyOn(Array, 'from');
      const customSanitize = createSanitizeHandleIdCache(2);

      expect(customSanitize('A')).toBe('c-0041');
      expect(spy).toHaveBeenCalledTimes(1);

      expect(customSanitize('B')).toBe('c-0042');
      expect(spy).toHaveBeenCalledTimes(2);

      expect(customSanitize('A')).toBe('c-0041');
      expect(spy).toHaveBeenCalledTimes(2);

      expect(customSanitize('C')).toBe('c-0043');
      expect(spy).toHaveBeenCalledTimes(3);

      expect(customSanitize('A')).toBe('c-0041');
      expect(spy).toHaveBeenCalledTimes(3);

      expect(customSanitize('C')).toBe('c-0043');
      expect(spy).toHaveBeenCalledTimes(3);

      expect(customSanitize('B')).toBe('c-0042');
      expect(spy).toHaveBeenCalledTimes(4);
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
