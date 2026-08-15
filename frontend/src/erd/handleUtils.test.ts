import { describe, it, expect } from 'vitest';
import { parseColumnNameFromHandle, sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils';

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
      const handle = sourceColumnHandleId('user_id');
      expect(parseColumnNameFromHandle(handle)).toBe('user_id');
    });

    it('should parse target handle correctly', () => {
      const handle = targetColumnHandleId('id_가');
      expect(parseColumnNameFromHandle(handle)).toBe('id_가');
    });

    it('should parse empty string handle correctly', () => {
      const handle = sourceColumnHandleId('');
      expect(parseColumnNameFromHandle(handle)).toBe('');
    });

    it('should parse emoji correctly', () => {
      const handle = targetColumnHandleId('id_🚀');
      expect(parseColumnNameFromHandle(handle)).toBe('id_🚀');
    });

    it('should return null for invalid handles', () => {
      expect(parseColumnNameFromHandle(null)).toBeNull();
      expect(parseColumnNameFromHandle(undefined)).toBeNull();
      expect(parseColumnNameFromHandle('invalid-handle')).toBeNull();
      expect(parseColumnNameFromHandle('src-invalid')).toBeNull();
    });
  });
});
