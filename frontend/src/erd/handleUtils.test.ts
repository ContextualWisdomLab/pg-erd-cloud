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
    it('should parse an ascii string', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064')).toBe('id');
      expect(parseColumnNameFromHandle('tgt-c-0069-0064')).toBe('id');
    });

    it('should parse empty string', () => {
      expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
    });

    it('should parse special characters', () => {
      expect(parseColumnNameFromHandle('src-c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
    });

    it('should parse unicode characters', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064-005f-ac00')).toBe('id_가');
    });

    it('should parse emojis', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064-005f-1f680')).toBe('id_🚀');
    });

    it('should return null for invalid handle formats', () => {
      expect(parseColumnNameFromHandle('')).toBeNull();
      expect(parseColumnNameFromHandle('invalid')).toBeNull();
      expect(parseColumnNameFromHandle('src-x-0069-0064')).toBeNull();
    });

    it('should return null for invalid hex sequences', () => {
      for (const handle of [
        'src-c-zzzz',
        'src-c-0069x',
        'src-c-empty-0069',
        'foo-c-0069',
        'src-c--0069',
        'src-c-69',
        'src-c-110000',
      ]) {
        expect(parseColumnNameFromHandle(handle)).toBeNull();
      }
    });
  });
});
