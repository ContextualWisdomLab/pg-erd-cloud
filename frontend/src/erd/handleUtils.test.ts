import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils';

// Reference implementation (prior scalar-map contract) for property testing
function referenceSanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

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

    it('should handle combining marks', () => {
      expect(sanitizeHandleId('e\u0301')).toBe('c-0065-0301');
    });

    it('should handle lone high/low surrogates', () => {
      expect(sanitizeHandleId('\uD800')).toBe('c-d800');
      expect(sanitizeHandleId('\uDC00')).toBe('c-dc00');
    });

    it('should handle long bounded identifiers', () => {
      const longId = 'a'.repeat(200);
      expect(sanitizeHandleId(longId)).toBe('c-' + Array(200).fill('0061').join('-'));
    });

    it('should match reference implementation for arbitrary unicode strings', () => {
      fc.assert(
        fc.property(fc.string(), (str) => {
          expect(sanitizeHandleId(str)).toBe(referenceSanitizeHandleId(str));
        })
      );
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
