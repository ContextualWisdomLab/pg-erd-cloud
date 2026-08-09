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

    it.each([
      ['id123', 'c-0069-0064-0031-0032-0033'],
      ['user id', 'c-0075-0073-0065-0072-0020-0069-0064'],
      ['!@#$%', 'c-0021-0040-0023-0024-0025'],
      ['\n\t', 'c-000a-0009'],
      ['e\u0301', 'c-0065-0301'],
      ['👨‍👩‍👦', 'c-1f468-200d-1f469-200d-1f466'],
    ])('encodes every Unicode scalar in %j', (input, expected) => {
      expect(sanitizeHandleId(input)).toBe(expected);
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
    it('decodes simple ascii', () => {
      expect(parseColumnNameFromHandle('src-c-0069-0064')).toBe('id');
    });
    it('decodes empty', () => {
      expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
    });
    it('returns null for bad formats', () => {
      expect(parseColumnNameFromHandle('bad-format')).toBe(null);
      expect(parseColumnNameFromHandle(null as any)).toBe(null);
      expect(parseColumnNameFromHandle(undefined as any)).toBe(null);
    });
    it('returns null for excessively long strings to prevent DoS', () => {
      expect(parseColumnNameFromHandle('src-c-' + '0069-'.repeat(150))).toBe(null);
    });
  });
});
