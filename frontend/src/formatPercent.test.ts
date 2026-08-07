import { describe, it, expect } from 'vitest';
import { formatPercent } from './App';

describe('formatPercent', () => {
  it('should format numeric values as percentages correctly', () => {
    // Basic positive values
    expect(formatPercent(0.5)).toBe('50%');
    expect(formatPercent(1)).toBe('100%');
    expect(formatPercent(1.5)).toBe('150%');
    expect(formatPercent(2)).toBe('200%');

    // Zero
    expect(formatPercent(0)).toBe('0%');

    // Negative values
    expect(formatPercent(-0.5)).toBe('-50%');
    expect(formatPercent(-1)).toBe('-100%');

    // Rounding edge cases
    expect(formatPercent(0.3333333)).toBe('33%');
    expect(formatPercent(0.6666667)).toBe('67%');
    expect(formatPercent(0.125)).toBe('13%'); // 12.5 rounded up to 13
    expect(formatPercent(0.124)).toBe('12%'); // 12.4 rounded down to 12
    expect(formatPercent(-0.125)).toBe('-12%'); // -12.5 rounded towards zero in JS (Math.round(-12.5) is -12)
    expect(formatPercent(-0.126)).toBe('-13%'); // -12.6 rounded to -13
  });
});
