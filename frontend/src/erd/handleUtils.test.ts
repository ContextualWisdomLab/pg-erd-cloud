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
    it('should parse simple ascii string from src handle', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064')).toBe('id');
    });

    it('should parse simple ascii string from tgt handle', () => {
      expect(parseColumnNameFromHandle('tgt-c-0069-0064')).toBe('id');
    });

    it('should parse simple ascii string from raw handle', () => {
      expect(parseColumnNameFromHandle('c-0069-0064')).toBe('id');
    });

    it('should parse empty string handle', () => {
      expect(parseColumnNameFromHandle('c-empty')).toBe('');
      expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
    });

    it('should handle special characters', () => {
      expect(parseColumnNameFromHandle('c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
    });

    it('should handle unicode characters', () => {
      expect(parseColumnNameFromHandle('c-0069-0064-005f-ac00')).toBe('id_가');
    });

    it('should handle emojis', () => {
      expect(parseColumnNameFromHandle('c-0069-0064-005f-1f680')).toBe('id_🚀');
    });

    it('should return null for invalid handles', () => {
      expect(parseColumnNameFromHandle(null)).toBeNull();
      expect(parseColumnNameFromHandle(undefined)).toBeNull();
      expect(parseColumnNameFromHandle('')).toBeNull();
    });

    it('should return raw string for legacy unencoded handles', () => {
      expect(parseColumnNameFromHandle('invalid-format')).toBe('invalid-format');
      expect(parseColumnNameFromHandle('src-invalid-format')).toBe('invalid-format');
    });
  });
});
