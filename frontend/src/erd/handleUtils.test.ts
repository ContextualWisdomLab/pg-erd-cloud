import { describe, it, expect } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, decodeHandleId, decodeSourceHandleId, decodeTargetHandleId } from './handleUtils';

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

  describe('decodeHandleId', () => {
    it('should decode a simple ascii string', () => {
      expect(decodeHandleId('c-0069-0064')).toBe('id');
    });

    it('should handle empty string', () => {
      expect(decodeHandleId('c-empty')).toBe('');
    });

    it('should handle special characters', () => {
      expect(decodeHandleId('c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
    });

    it('should handle unicode characters', () => {
      expect(decodeHandleId('c-0069-0064-005f-ac00')).toBe('id_가');
    });

    it('should handle emojis', () => {
      expect(decodeHandleId('c-0069-0064-005f-1f680')).toBe('id_🚀');
    });

    it('should return original if format does not match', () => {
      expect(decodeHandleId('invalid-handle')).toBe('invalid-handle');
    });
  });

  describe('decodeSourceHandleId', () => {
    it('should strip src- and decode', () => {
      expect(decodeSourceHandleId('src-c-0069-0064')).toBe('id');
    });

    it('should return original if format does not match', () => {
      expect(decodeSourceHandleId('invalid-handle')).toBe('invalid-handle');
    });
  });

  describe('decodeTargetHandleId', () => {
    it('should strip tgt- and decode', () => {
      expect(decodeTargetHandleId('tgt-c-0069-0064')).toBe('id');
    });

    it('should return original if format does not match', () => {
      expect(decodeTargetHandleId('invalid-handle')).toBe('invalid-handle');
    });
  });
});
