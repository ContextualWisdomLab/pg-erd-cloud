import { describe, expect, it } from 'vitest';
import { calculateStats } from './handleUtils.benchmark';

describe('calculateStats', () => {
  it('averages the two middle values for an even sample count', () => {
    const samples = [4, 1, 3, 2];

    expect(calculateStats(samples)).toEqual({
      mean: 2.5,
      median: 2.5,
      raw: [1, 2, 3, 4],
    });
    expect(samples).toEqual([4, 1, 3, 2]);
  });

  it('uses the middle value for an odd sample count', () => {
    expect(calculateStats([9, 1, 3])).toEqual({
      mean: 13 / 3,
      median: 3,
      raw: [1, 3, 9],
    });
  });
});
