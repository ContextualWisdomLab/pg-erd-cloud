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
    it('should handle null or undefined', () => {
      expect(parseColumnNameFromHandle(null)).toBeNull();
      expect(parseColumnNameFromHandle(undefined)).toBeNull();
    });

    it('should handle empty base handles', () => {
      expect(parseColumnNameFromHandle('c-empty')).toBe('');
    });

    it('should handle empty source handles', () => {
      expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
    });

    it('should parse a base handle id', () => {
      expect(parseColumnNameFromHandle('c-0069-0064')).toBe('id');
    });

    it('should parse a source handle id', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064')).toBe('id');
    });

    it('should parse a target handle id', () => {
      expect(parseColumnNameFromHandle('tgt-c-0069-0064')).toBe('id');
    });

    it('should parse special and unicode characters', () => {
      expect(parseColumnNameFromHandle('c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
      expect(parseColumnNameFromHandle('c-0069-0064-005f-ac00')).toBe('id_가');
      expect(parseColumnNameFromHandle('tgt-c-0069-0064-005f-1f680')).toBe('id_🚀');
    });
  });
});
