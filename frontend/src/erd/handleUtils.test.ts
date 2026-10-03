import { describe, it, expect, vi } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, createHandleCache } from './handleUtils';

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

  describe('createHandleCache', () => {
    it('evicts the least recently used entry when full', () => {
      const codePointSpy = vi.spyOn(String.prototype, 'codePointAt');
      const cache = createHandleCache(2);
      expect(cache('a')).toBe('c-0061');
      expect(cache('b')).toBe('c-0062');
      expect(cache('a')).toBe('c-0061');
      expect(cache('c')).toBe('c-0063');
      expect(cache('b')).toBe('c-0062');

      expect(codePointSpy).toHaveBeenCalledTimes(4);
      codePointSpy.mockRestore();
    });

    it('does not retain entries when capacity is zero', () => {
      const codePointSpy = vi.spyOn(String.prototype, 'codePointAt');
      const cache = createHandleCache(0);

      expect(cache('a')).toBe('c-0061');
      expect(cache('a')).toBe('c-0061');

      expect(codePointSpy).toHaveBeenCalledTimes(2);
      codePointSpy.mockRestore();
    });

    it.each([-1, 1.5, Number.NaN, Number.POSITIVE_INFINITY])(
      'rejects invalid capacity %s',
      (capacity) => {
        expect(() => createHandleCache(capacity)).toThrow(RangeError);
      },
    );
  });
});
