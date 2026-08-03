import { describe, it, expect } from 'vitest';
import { parseColumnNameFromHandle, sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils';

describe('handleUtils', () => {
  describe('parseColumnNameFromHandle', () => {
    it('should decode a simple ascii string', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064')).toBe('id');
      expect(parseColumnNameFromHandle('tgt-c-0069-0064')).toBe('id');
      expect(parseColumnNameFromHandle('c-0069-0064')).toBe('id');
    });

    it('should handle empty string', () => {
      expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
      expect(parseColumnNameFromHandle('c-empty')).toBe('');
    });

    it('should handle special characters', () => {
      expect(parseColumnNameFromHandle('src-c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
    });

    it('should handle unicode characters', () => {
      expect(parseColumnNameFromHandle('tgt-c-0069-0064-005f-ac00')).toBe('id_가');
    });

    it('should handle emojis', () => {
      expect(parseColumnNameFromHandle('c-0069-0064-005f-1f680')).toBe('id_🚀');
    });

    it('should return null for invalid prefix or format', () => {
      expect(parseColumnNameFromHandle('invalid-format')).toBeNull();
      expect(parseColumnNameFromHandle('src-x-0069')).toBeNull();
    });

    it('should return null for invalid hex sequences', () => {
      expect(parseColumnNameFromHandle('src-c-zzzz')).toBeNull();
    });
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
