import { describe, it, expect } from 'vitest';
import { calculateCardinalityRatio, classifyCardinality } from '../cardinality';

describe('calculateCardinalityRatio', () => {
  it('calculates normal ratios', () => {
    expect(calculateCardinalityRatio(100, 20)).toBe(0.2);
    expect(calculateCardinalityRatio(100, 50)).toBe(0.5);
    expect(calculateCardinalityRatio(100, 100)).toBe(1);
  });

  it('returns 0 for zero or negative inputs', () => {
    expect(calculateCardinalityRatio(0, 10)).toBe(0);
    expect(calculateCardinalityRatio(100, 0)).toBe(0);
    expect(calculateCardinalityRatio(-100, 10)).toBe(0);
    expect(calculateCardinalityRatio(100, -10)).toBe(0);
  });

  it('clamps ratios greater than 1', () => {
    expect(calculateCardinalityRatio(100, 150)).toBe(1);
  });

  it('returns 0 for non-finite inputs', () => {
    expect(calculateCardinalityRatio(Infinity, 10)).toBe(0);
    expect(calculateCardinalityRatio(10, Infinity)).toBe(0);
  });
});

describe('classifyCardinality', () => {
  it('should return "recommended" when ratio is >= 0.2', () => {
    expect(classifyCardinality(0.2)).toBe('recommended');
    expect(classifyCardinality(0.5)).toBe('recommended');
    expect(classifyCardinality(1.0)).toBe('recommended');
  });

  it('should return "consider" when ratio is >= 0.05 and < 0.2', () => {
    expect(classifyCardinality(0.05)).toBe('consider');
    expect(classifyCardinality(0.1)).toBe('consider');
    expect(classifyCardinality(0.199)).toBe('consider');
  });

  it('should return "skip" when ratio is < 0.05', () => {
    expect(classifyCardinality(0.049)).toBe('skip');
    expect(classifyCardinality(0.01)).toBe('skip');
    expect(classifyCardinality(0)).toBe('skip');
  });
});
