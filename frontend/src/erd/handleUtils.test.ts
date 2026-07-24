import { describe, it, expect } from 'vitest';
import {
  decodeHandleId,
  decodeSourceHandleId,
  decodeTargetHandleId,
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

    it('should handle c-empty', () => {
      expect(decodeHandleId('c-empty')).toBe('');
    });

    it('should return empty string for invalid prefix', () => {
      expect(decodeHandleId('invalid-prefix')).toBe('');
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
  });

  describe('decodeSourceHandleId', () => {
    it('should decode a valid src handle', () => {
      expect(decodeSourceHandleId('src-c-0069-0064')).toBe('id');
    });

    it('should return null for null/undefined/invalid prefix', () => {
      expect(decodeSourceHandleId(null)).toBeNull();
      expect(decodeSourceHandleId(undefined)).toBeNull();
      expect(decodeSourceHandleId('tgt-c-0069-0064')).toBeNull();
    });
  });

  describe('decodeTargetHandleId', () => {
    it('should decode a valid tgt handle', () => {
      expect(decodeTargetHandleId('tgt-c-0069-0064')).toBe('id');
    });

    it('should return null for null/undefined/invalid prefix', () => {
      expect(decodeTargetHandleId(null)).toBeNull();
      expect(decodeTargetHandleId(undefined)).toBeNull();
      expect(decodeTargetHandleId('src-c-0069-0064')).toBeNull();
    });
  });
});
