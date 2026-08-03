import { describe, expect, it } from 'vitest';

import {
  decodeHandleId,
  sanitizeHandleId,
  sourceColumnHandleId,
  targetColumnHandleId,
} from './handleUtils';

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it('should encode a simple ascii string', () => {
      expect(sanitizeHandleId('id')).toBe('c-0069-0064');
    });

    it('should handle empty string', () => {
      expect(sanitizeHandleId('')).toBe('c-empty');
    });

    it('should handle special characters', () => {
      expect(sanitizeHandleId('user_id')).toBe(
        'c-0075-0073-0065-0072-005f-0069-0064',
      );
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

  describe('decodeHandleId', () => {
    it('decodes canonical bare, source, and target handles', () => {
      expect(decodeHandleId('c-0069-0064')).toBe('id');
      expect(decodeHandleId('src-c-0069-0064')).toBe('id');
      expect(decodeHandleId('tgt-c-0069-0064')).toBe('id');
    });

    it('decodes empty, special, unicode, emoji, and uppercase chunks', () => {
      expect(decodeHandleId('c-empty')).toBe('');
      expect(decodeHandleId('src-c-empty')).toBe('');
      expect(
        decodeHandleId('c-0075-0073-0065-0072-005f-0069-0064'),
      ).toBe('user_id');
      expect(decodeHandleId('c-0069-0064-005f-ac00')).toBe('id_가');
      expect(decodeHandleId('c-0069-0064-005f-1f680')).toBe('id_🚀');
      expect(decodeHandleId('c-006A')).toBe('j');
    });

    it('round-trips values emitted by the encoder', () => {
      for (const value of ['', 'id', 'user_id', 'id_가', 'id_🚀']) {
        expect(decodeHandleId(sanitizeHandleId(value))).toBe(value);
      }
    });

    it('rejects missing, malformed, non-canonical, and out-of-range handles', () => {
      expect(decodeHandleId(null)).toBeNull();
      expect(decodeHandleId(undefined)).toBeNull();
      expect(decodeHandleId('')).toBeNull();
      expect(decodeHandleId('invalid-format')).toBeNull();
      expect(decodeHandleId('src-c')).toBeNull();
      expect(decodeHandleId('prefix-src-c-0069')).toBeNull();
      expect(decodeHandleId('src-c-0069xyz')).toBeNull();
      expect(decodeHandleId('src-c-0069-empty')).toBeNull();
      expect(decodeHandleId('src-c-69')).toBeNull();
      expect(decodeHandleId('src-c-000069')).toBeNull();
      expect(decodeHandleId('src-c-110000')).toBeNull();
    });
  });
});
