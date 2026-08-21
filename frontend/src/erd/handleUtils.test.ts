import { describe, it, expect } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, parseColumnNameFromHandle } from './handleUtils';

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

  describe('parseColumnNameFromHandle', () => {
    it('should decode a simple ascii string', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064')).toBe('id');
      expect(parseColumnNameFromHandle('tgt-c-0069-0064')).toBe('id');
    });

    it('should handle empty string', () => {
      expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
      expect(parseColumnNameFromHandle('tgt-c-empty')).toBe('');
    });

    it('should handle special characters', () => {
      expect(parseColumnNameFromHandle('src-c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
    });

    it('should handle unicode characters', () => {
      expect(parseColumnNameFromHandle('tgt-c-0069-0064-005f-ac00')).toBe('id_가');
    });

    it('should handle emojis', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064-005f-1f680')).toBe('id_🚀');
    });

    it.each([
      'src-user_id',
      'id',
      'c-0069-0064',
      'foo-c-0069',
      'src-c-0069junk',
      'src-c-0069-',
      'src-c-empty-0069',
      'src-c-d800',
      'src-c-110000',
    ])('should reject non-canonical handle %s', (handle) => {
      expect(parseColumnNameFromHandle(handle)).toBe(null);
    });

    it('should handle null/undefined', () => {
      expect(parseColumnNameFromHandle(null)).toBe(null);
      expect(parseColumnNameFromHandle(undefined)).toBe(null);
    });

    it.each([
      'c-zz',
      'c-0069-zz',
      'c-0069-',
      'c-0069junk',
      'c-0g69-0064',
    ])('should reject malformed hexadecimal handle %s', (handle) => {
      expect(parseColumnNameFromHandle(handle)).toBe(null);
    });
  });
});
