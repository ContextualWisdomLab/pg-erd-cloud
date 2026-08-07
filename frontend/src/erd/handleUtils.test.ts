import { describe, it, expect } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, decodeHandleId } from './handleUtils';

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

  describe('decodeHandleId', () => {
    it('should decode a simple ascii string', () => {
      expect(decodeHandleId('c-0069-0064')).toBe('id');
      expect(decodeHandleId('src-c-0069-0064')).toBe('id');
      expect(decodeHandleId('tgt-c-0069-0064')).toBe('id');
    });

    it('should handle empty string', () => {
      expect(decodeHandleId('c-empty')).toBe('');
      expect(decodeHandleId('src-c-empty')).toBe('');
    });

    it('should handle special characters', () => {
      expect(decodeHandleId('c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
    });

    it('should handle unicode characters', () => {
      expect(decodeHandleId('c-0069-0064-005f-ac00')).toBe('id_가');
    });

    it('should handle emojis', () => {
      expect(decodeHandleId('c-0069-0064-005f-1f680')).toBe('id_🚀');
    });

    it('should handle null/undefined/invalid values gracefully', () => {
      expect(decodeHandleId(null)).toBeNull();
      expect(decodeHandleId(undefined)).toBeNull();
      expect(decodeHandleId('')).toBeNull();
      expect(decodeHandleId('invalid-format')).toBeNull();
      expect(decodeHandleId('src-c')).toBeNull(); // Missing hex parts
    });

    it('should reject non-canonical hex and prefixes', () => {
      // Uppercase hex
      expect(decodeHandleId('c-0069-006A')).toBeNull();
      // Junk in hex
      expect(decodeHandleId('c-0069junk-0064')).toBeNull();
      // Arbitrary prefix
      expect(decodeHandleId('foo-c-0069')).toBeNull();
      // Empty chunk mix
      expect(decodeHandleId('c-empty-0069')).toBeNull();
      // Out of bounds code point
      expect(decodeHandleId('c-200000')).toBeNull();
      // Missing hex chunk data between separators
      expect(decodeHandleId('c-0069--0064')).toBeNull();
    });
  });
});

  it('limits payload and hex chunks size against ReDoS', () => {
    expect(decodeHandleId('c-' + '0041-'.repeat(20000) + '0041')).toBeNull();
  });
