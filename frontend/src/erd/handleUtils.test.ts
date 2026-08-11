import { describe, expect, it } from 'vitest';

import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, parseColumnNameFromHandle } from './handleUtils';

describe('handleUtils', () => {
  describe('sanitizeHandleId', () => {
    it('should correctly encode ASCII characters', () => {
      expect(sanitizeHandleId('id')).toBe('c-0069-0064');
    });

    it('should correctly encode Unicode characters', () => {
      expect(sanitizeHandleId('테스트')).toBe('c-d14c-c2a4-d2b8');
    });

    it('should correctly handle empty strings', () => {
      expect(sanitizeHandleId('')).toBe('c-empty');
    });
  });

  describe('sourceColumnHandleId', () => {
    it('should prepend src- to the sanitized handle', () => {
      expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064');
    });
  });

  describe('targetColumnHandleId', () => {
    it('should prepend tgt- to the sanitized handle', () => {
      expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064');
    });
  });

  describe('parseColumnNameFromHandle', () => {
    it('should parse source handle correctly', () => {
      expect(parseColumnNameFromHandle(sourceColumnHandleId('my_column'))).toBe('my_column');
    });

    it('should parse target handle correctly', () => {
      expect(parseColumnNameFromHandle(targetColumnHandleId('my_column'))).toBe('my_column');
    });

    it('should handle unicode characters', () => {
      expect(parseColumnNameFromHandle(sourceColumnHandleId('테스트'))).toBe('테스트');
    });

    it('should return empty string for empty input', () => {
      expect(parseColumnNameFromHandle(sourceColumnHandleId(''))).toBe('');
    });

    it('should return null for invalid handles', () => {
      expect(parseColumnNameFromHandle('invalid-handle')).toBeNull();
      expect(parseColumnNameFromHandle(null)).toBeNull();
      expect(parseColumnNameFromHandle(undefined)).toBeNull();
    });
  });
});
