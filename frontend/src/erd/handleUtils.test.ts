import { describe, it, expect } from 'vitest';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, parseSourceColumnNameFromHandle, parseTargetColumnNameFromHandle } from './handleUtils';

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


  describe('parseSourceColumnNameFromHandle', () => {
    it('should parse ordinary strings', () => {
      expect(parseSourceColumnNameFromHandle('src-c-0069-0064')).toBe('id');
      expect(parseSourceColumnNameFromHandle('src-c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
    });

    it('should parse empty string handle', () => {
      expect(parseSourceColumnNameFromHandle('src-c-empty')).toBe('');
    });

    it('should parse non-BMP characters', () => {
      expect(parseSourceColumnNameFromHandle('src-c-0069-0064-005f-1f680')).toBe('id_🚀');
    });

    it('should reject wrong-direction prefix', () => {
      expect(parseSourceColumnNameFromHandle('tgt-c-0069-0064')).toBeNull();
      expect(parseTargetColumnNameFromHandle('src-c-0069-0064')).toBeNull();
    });

    it('should reject bare c- without direction prefix', () => {
      expect(parseSourceColumnNameFromHandle('c-0069-0064')).toBeNull();
    });

    it('should reject partial-hex or trailing characters', () => {
      expect(parseSourceColumnNameFromHandle('src-c-0061junk')).toBeNull();
      expect(parseSourceColumnNameFromHandle('src-c-006')).toBeNull();
    });

    it('should reject empty segments', () => {
      expect(parseSourceColumnNameFromHandle('src-c-0069--0064')).toBeNull();
    });

    it('should reject over-range hex', () => {
      expect(parseSourceColumnNameFromHandle('src-c-110000')).toBeNull();
    });

    it('should reject surrogate range hex', () => {
      expect(parseSourceColumnNameFromHandle('src-c-d800')).toBeNull();
      expect(parseSourceColumnNameFromHandle('src-c-dfff')).toBeNull();
    });

    it('should reject noncanonical forms', () => {
      expect(parseSourceColumnNameFromHandle('src-c-061')).toBeNull(); // Missing padding
      expect(parseSourceColumnNameFromHandle('src-c-00000061')).toBeNull(); // Over padding
      expect(parseSourceColumnNameFromHandle('src-c-006A')).toBeNull(); // Uppercase
    });
  });

  describe('parseTargetColumnNameFromHandle', () => {
    it('should parse ordinary target handles', () => {
      expect(parseTargetColumnNameFromHandle('tgt-c-0069-0064')).toBe('id');
    });
  });
});
