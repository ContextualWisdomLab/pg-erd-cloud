import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { sanitizeHandleId, sourceColumnHandleId, targetColumnHandleId, parseColumnNameFromHandle } from '../handleUtils';

describe('Handle encoding/decoding properties', () => {
  it('should round-trip correctly for arbitrary valid column names (including ASCII, CJK, emoji, punctuation)', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 0 }), (str) => {
        const sourceHandle = sourceColumnHandleId(str);
        const parsedSource = parseColumnNameFromHandle(sourceHandle);
        expect(parsedSource).toBe(str);

        const targetHandle = targetColumnHandleId(str);
        const parsedTarget = parseColumnNameFromHandle(targetHandle);
        expect(parsedTarget).toBe(str);
      })
    );
  });

  it('should handle malformed handles safely by returning null', () => {
    expect(parseColumnNameFromHandle(null)).toBeNull();
    expect(parseColumnNameFromHandle(undefined)).toBeNull();
    expect(parseColumnNameFromHandle('')).toBeNull();
    expect(parseColumnNameFromHandle('invalid-format')).toBeNull();
    expect(parseColumnNameFromHandle('src-c-nothex')).toBeNull();
  });
});
