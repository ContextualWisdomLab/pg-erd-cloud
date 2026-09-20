import { describe, it, expect } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils';

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it('sanitizes a simple string', () => {
      expect(sanitizeHandleId('id')).toBe('c-0069-0064');
    });

    it('handles empty strings', () => {
      expect(sanitizeHandleId('')).toBe('c-empty');
    });

    it('sanitizes a complex string', () => {
      expect(sanitizeHandleId('user_id')).toBe('c-0075-0073-0065-0072-005f-0069-0064');
    });

    it('handles non-ascii characters (Korean)', () => {
      expect(sanitizeHandleId('id_가')).toBe('c-0069-0064-005f-ac00');
    });

    it('handles supplementary code points (emoji)', () => {
      expect(sanitizeHandleId('id_🚀')).toBe('c-0069-0064-005f-1f680');
    });

    it('returns consistent results for repeated calls (cache hit)', () => {
      expect(sanitizeHandleId('test_hit')).toBe('c-0074-0065-0073-0074-005f-0068-0069-0074');
      expect(sanitizeHandleId('test_hit')).toBe('c-0074-0065-0073-0074-005f-0068-0069-0074');
    });

    it('rejects strings longer than 255 characters', () => {
      const longString = 'a'.repeat(256);
      expect(sanitizeHandleId(longString)).toBe('c-empty');
    });
  });

  describe('sourceColumnHandleId', () => {
    it('prepends src-', () => {
      expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064');
    });
  });

  describe('targetColumnHandleId', () => {
    it('prepends tgt-', () => {
      expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064');
    });
  });
});
