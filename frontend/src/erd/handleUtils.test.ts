import { describe, expect, it } from 'vitest';
import {
  sanitizeHandleId,
  sourceColumnHandleId,
  targetColumnHandleId,
  decodeHandleId,
} from './handleUtils';

describe('sanitizeHandleId', () => {
  it('should encode a regular string', () => {
    expect(sanitizeHandleId('id')).toBe('c-0069-0064');
  });

  it('should encode a string with uppercase letters', () => {
    expect(sanitizeHandleId('ID')).toBe('c-0049-0044');
  });

  it('should return c-empty for an empty string', () => {
    expect(sanitizeHandleId('')).toBe('c-empty');
  });
});

describe('sourceColumnHandleId', () => {
  it('should return the correct source handle id', () => {
    expect(sourceColumnHandleId('id')).toBe('src-c-0069-0064');
  });
});

describe('targetColumnHandleId', () => {
  it('should return the correct target handle id', () => {
    expect(targetColumnHandleId('id')).toBe('tgt-c-0069-0064');
  });
});

describe('decodeHandleId', () => {
  it('should decode a regular handle id', () => {
    expect(decodeHandleId('c-0069-0064')).toBe('id');
  });

  it('should decode a source handle id', () => {
    expect(decodeHandleId('src-c-0069-0064')).toBe('id');
  });

  it('should decode a target handle id', () => {
    expect(decodeHandleId('tgt-c-0069-0064')).toBe('id');
  });

  it('should decode tgt-c-empty correctly', () => {
    expect(decodeHandleId('tgt-c-empty')).toBe('');
  });

  it('should round-trip lone-surrogate successfully or return null gracefully', () => {
    const codePoint = 0xD800; // Lone surrogate
    const handle = 'c-' + codePoint.toString(16).padStart(4, '0');
    expect(decodeHandleId(handle)).toBeNull(); // String.fromCodePoint throws RangeError
  });

  it('should reject exact c-0069-0064junk', () => {
    expect(decodeHandleId('c-0069-0064junk')).toBeNull();
  });

  it('should reject invalid prefixes', () => {
    expect(decodeHandleId('invalid-c-0069-0064')).toBeNull();
    expect(decodeHandleId('src-invalid-0069-0064')).toBeNull();
  });

  it('should reject empty chunks', () => {
    expect(decodeHandleId('c-0069--0064')).toBeNull();
  });

  it('should reject uppercase hex characters', () => {
    expect(decodeHandleId('c-0069-006A')).toBeNull(); // A is uppercase
  });

  it('should reject out of range code points like 0x110000', () => {
    expect(decodeHandleId('c-110000')).toBeNull();
  });

  it('should return null for null/undefined/empty input', () => {
    expect(decodeHandleId(null)).toBeNull();
    expect(decodeHandleId(undefined)).toBeNull();
    expect(decodeHandleId('')).toBeNull();
  });

  it('should limit payload size against ReDoS', () => {
    expect(decodeHandleId('c-' + '0041-'.repeat(20000) + '0041')).toBeNull();
  });
});
