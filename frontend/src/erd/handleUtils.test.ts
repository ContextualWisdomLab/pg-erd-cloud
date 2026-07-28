import { describe, it, expect } from 'vitest';
import {
  sanitizeHandleId,
  sourceColumnHandleId,
  targetColumnHandleId,
  decodeHandleId,
  decodeSourceHandleId,
  decodeTargetHandleId,
} from './handleUtils';

describe('handleUtils', () => {
  it('encodes handles in exact hex format', () => {
    // Retain explicit strict tests for backward compatibility
    expect(sanitizeHandleId("id")).toBe("c-0069-0064");
    expect(sourceColumnHandleId("id")).toBe("src-c-0069-0064");
    expect(targetColumnHandleId("id")).toBe("tgt-c-0069-0064");
  });

  it('encodes and decodes handles correctly', () => {
    const colName1 = "user_id";
    const src1 = sourceColumnHandleId(colName1);
    const tgt1 = targetColumnHandleId(colName1);

    expect(decodeSourceHandleId(src1)).toBe(colName1);
    expect(decodeTargetHandleId(tgt1)).toBe(colName1);
    expect(decodeHandleId(sanitizeHandleId(colName1))).toBe(colName1);
  });

  it('handles empty strings', () => {
    const colNameEmpty = "";
    const srcEmpty = sourceColumnHandleId(colNameEmpty);
    expect(decodeSourceHandleId(srcEmpty)).toBe(colNameEmpty);
  });

  it('handles unicode characters', () => {
    const colNameUni = "사용자_아이디😎";
    const srcUni = sourceColumnHandleId(colNameUni);
    expect(decodeSourceHandleId(srcUni)).toBe(colNameUni);
  });

  it('returns null for invalid prefixes', () => {
    expect(decodeSourceHandleId('tgt-c-0069')).toBeNull();
    expect(decodeTargetHandleId('src-c-0069')).toBeNull();
    expect(decodeHandleId('invalid-0069')).toBeNull();
  });
});
