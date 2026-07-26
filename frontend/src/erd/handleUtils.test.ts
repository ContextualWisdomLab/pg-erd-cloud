import { expect, test, describe } from 'vitest';

import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, parseColumnNameFromHandle } from './handleUtils';

describe('sanitizeHandleId', () => {
  test('handles empty strings', () => {
    expect(sanitizeHandleId('')).toBe('c-empty');
  });

  test('encodes regular strings to hex code points', () => {
    // 'id' -> 0x69 0x64 -> 0069-0064
    expect(sanitizeHandleId('id')).toBe('c-0069-0064');
  });

  test('encodes snake_case strings', () => {
    // 'user_id' -> u=0075, s=0073, e=0065, r=0072, _=005f, i=0069, d=0064
    expect(sanitizeHandleId('user_id')).toBe('c-0075-0073-0065-0072-005f-0069-0064');
  });
});

describe('sourceColumnHandleId', () => {
  test('prefixes the sanitized id with src-', () => {
    expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064');
  });
});

describe('targetColumnHandleId', () => {
  test('prefixes the sanitized id with tgt-', () => {
    expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064');
  });
});

describe('parseColumnNameFromHandle', () => {
  test('parses source handle correctly', () => {
    expect(parseColumnNameFromHandle('src-c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
  });

  test('parses target handle correctly', () => {
    expect(parseColumnNameFromHandle('tgt-c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
  });

  test('parses naked handle correctly', () => {
    expect(parseColumnNameFromHandle('c-0075-0073-0065-0072-005f-0069-0064')).toBe('user_id');
  });

  test('returns empty string for c-empty', () => {
    expect(parseColumnNameFromHandle('src-c-empty')).toBe('');
  });

  test('returns null for invalid format', () => {
    expect(parseColumnNameFromHandle('invalid')).toBeNull();
  });
});
