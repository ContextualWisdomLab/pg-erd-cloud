import { describe, it, expect, vi, afterEach } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, createSanitizeHandleId } from './handleUtils';

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

  describe('sanitizeHandleId cache', () => {
    it('should cache repeated calls', () => {
      const spy = vi.spyOn(Array, 'from');
      const testCache = createSanitizeHandleId(2);
      testCache('col1');
      testCache('col1');
      expect(spy).toHaveBeenCalledTimes(1);
    });

    it('should evict oldest entry when exceeding max size', () => {
      const spy = vi.spyOn(Array, 'from');
      const testCache = createSanitizeHandleId(2);
      testCache('col1');
      testCache('col2');
      testCache('col3'); // evicts col1
      testCache('col1'); // miss
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
