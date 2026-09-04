import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, parseColumnNameFromHandle } from '../handleUtils';

describe('Handle encoding/decoding properties', () => {
  it('should round-trip correctly for arbitrary valid column names (including ASCII, CJK, emoji, punctuation)', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 0 }), (str) => {
        const sourceHandle = sourceColumnHandleId(str);
        const parsedSource = parseColumnNameFromHandle(sourceHandle, 'src');
        expect(parsedSource).toBe(str);

        const targetHandle = targetColumnHandleId(str);
        const parsedTarget = parseColumnNameFromHandle(targetHandle, 'tgt');
        expect(parsedTarget).toBe(str);
      })
    );
  });

  it('should reject malformed handles, noncanonical padded hex, missing digits, and direction mismatches', () => {
    // Malformed/empty
    expect(parseColumnNameFromHandle(null)).toBeNull();
    expect(parseColumnNameFromHandle(undefined)).toBeNull();
    expect(parseColumnNameFromHandle('')).toBeNull();
    expect(parseColumnNameFromHandle('invalid-format')).toBeNull();

    // Direction swaps
    expect(parseColumnNameFromHandle('tgt-c-0069-0064', 'src')).toBeNull();
    expect(parseColumnNameFromHandle('src-c-0069-0064', 'tgt')).toBeNull();

    // Invalid hex / bad scalars
    expect(parseColumnNameFromHandle('src-c-nothex')).toBeNull();
    expect(parseColumnNameFromHandle('src-c-g000')).toBeNull();
    expect(parseColumnNameFromHandle('src-c-1000000')).toBeNull(); // Out of range (> 0x10FFFF)

    // Non-canonical padding (e.g. 00069 instead of 0069)
    // The letter 'i' (0069 in hex)
    expect(parseColumnNameFromHandle('src-c-00069')).toBeNull();
    // Uppercase letters in hex (should be lowercase according to toString(16))
    // '006A' will round trip back to '006a'. Thus '006A' fails the round trip check.
    expect(parseColumnNameFromHandle('src-c-006A')).toBeNull();
  });
});
