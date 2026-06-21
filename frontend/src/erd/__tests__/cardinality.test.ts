import { describe, it, expect } from 'vitest';
import { classifyCardinality } from '../cardinality';

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
