import { describe, it, expect } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId } from './handleUtils';

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it.each([
      ['simple ascii string', 'id', 'id'],
      ['empty string', '', ''],
      ['special characters', 'user_id', 'user_id'],
      ['unicode characters', 'id_가', 'id__'],
      ['emojis', 'id_🚀', 'id___'],
      ['alphanumeric', 'id123', 'id123'],
      ['spaces', 'user id', 'user_id'],
      ['special symbols', '!@#$%', '_____'],
      ['control characters', '\n\t', '__'],
      ['combining characters', 'e\u0301', 'e_'],
      ['emoji with zwj', '👨‍👩‍👦', '________'],
    ])('should handle %s', (_, input, expected) => {
      expect(sanitizeHandleId(input)).toBe(expected);
    });
  });

  describe('sourceColumnHandleId', () => {
    it('should prepend src- to sanitized id', () => {
      expect(sourceColumnHandleId('id')).toBe('src-id');
    });
  });

  describe('targetColumnHandleId', () => {
    it('should prepend tgt- to sanitized id', () => {
      expect(targetColumnHandleId('id')).toBe('tgt-id');
    });
  });
});
