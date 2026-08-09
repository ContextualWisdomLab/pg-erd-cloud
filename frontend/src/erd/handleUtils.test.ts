import { describe, it, expect } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils';

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it.each([
      ['simple ascii string', 'id', 'c-0069-0064'],
      ['empty string', '', 'c-empty'],
      ['special characters', 'user_id', 'c-0075-0073-0065-0072-005f-0069-0064'],
      ['unicode characters', 'id_가', 'c-0069-0064-005f-ac00'],
      ['emojis', 'id_🚀', 'c-0069-0064-005f-1f680'],
      ['alphanumeric', 'id123', 'c-0069-0064-0031-0032-0033'],
      ['spaces', 'user id', 'c-0075-0073-0065-0072-0020-0069-0064'],
      ['special symbols', '!@#$%', 'c-0021-0040-0023-0024-0025'],
      ['control characters', '\n\t', 'c-000a-0009'],
      ['combining characters', 'e\u0301', 'c-0065-0301'],
      ['emoji with zwj', '👨‍👩‍👦', 'c-1f468-200d-1f469-200d-1f466'],
    ])('should handle %s', (_, input, expected) => {
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
});
