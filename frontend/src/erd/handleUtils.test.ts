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
    it('should parse source handle correctly', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064')).toBe('id');
    });

    it('should parse target handle correctly', () => {
      expect(parseColumnNameFromHandle('tgt-c-0069-0064')).toBe('id');
    });

    it('should return empty string for empty handle', () => {
      expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
    });

    it('should parse unicode characters', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064-005f-ac00')).toBe('id_가');
    });

    it('should return null for invalid format', () => {
      expect(parseColumnNameFromHandle('invalid-handle')).toBeNull();
    });

    it.each([
      'src-c-0069junk',
      'src-c-0069-',
      'src-c-empty-0069',
      'foo-c-0069',
      'src-c-d800',
      'src-c-110000',
    ])('should reject malformed or invalid code point handles: %s', (handle) => {
      expect(parseColumnNameFromHandle(handle)).toBeNull();
    });
  });
});
