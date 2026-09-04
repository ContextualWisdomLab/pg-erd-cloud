import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { sourceColumnHandleId, targetColumnHandleId, parseColumnNameFromHandle } from '../handleUtils';

describe('Handle encoding/decoding properties', () => {
  it('round-trips arbitrary valid column names, including Unicode', () => {
    fc.assert(
      fc.property(fc.string({ minLength: 0 }), (str) => {
        const sourceHandle = sourceColumnHandleId(str);
        expect(parseColumnNameFromHandle(sourceHandle)).toBe(str);

        const targetHandle = targetColumnHandleId(str);
        expect(parseColumnNameFromHandle(targetHandle)).toBe(str);
      })
    );
  });

  it('rejects malformed and noncanonical handles instead of decoding partial values', () => {
    const malformedHandles = [
      null,
      undefined,
      '',
      'invalid-format',
      'src-c-nothex',
      'src-c-0041junk',
      'src-c-0041--0042',
      'src-c-000041',
      'src-c-004A',
      'src-c-110000',
      'src-c-d800',
    ] as const;

    for (const handle of malformedHandles) {
      expect(parseColumnNameFromHandle(handle)).toBeNull();
    }
  });
});
