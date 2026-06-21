import { describe, it, expect } from 'vitest';
import { calculateCardinalityRatio } from '../cardinality';

describe('calculateCardinalityRatio', () => {
  it('calculates normal ratio correctly', () => {
    // Expected args: rowCount, distinctCount
    expect(calculateCardinalityRatio(100, 20)).toBe(0.2);
    expect(calculateCardinalityRatio(100, 50)).toBe(0.5);
    expect(calculateCardinalityRatio(100, 100)).toBe(1.0);
  });

  it('returns 0 when rowCount is 0', () => {
    expect(calculateCardinalityRatio(0, 10)).toBe(0);
  });

  it('returns 0 when distinctCount is 0', () => {
    expect(calculateCardinalityRatio(100, 0)).toBe(0);
  });

  it('returns 0 when rowCount is negative', () => {
    expect(calculateCardinalityRatio(-100, 10)).toBe(0);
  });

  it('returns 0 when distinctCount is negative', () => {
    expect(calculateCardinalityRatio(100, -10)).toBe(0);
  });

  it('clamps ratio to 1.0 when distinctCount > rowCount', () => {
    expect(calculateCardinalityRatio(100, 150)).toBe(1.0);
  });

  it('handles Infinity correctly', () => {
    expect(calculateCardinalityRatio(Infinity, 10)).toBe(0);
    expect(calculateCardinalityRatio(10, Infinity)).toBe(0);
  });
});
