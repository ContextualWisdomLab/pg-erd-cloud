import { describe, it, expect } from 'vitest';
import { buildIndexRecommendations, classifyCardinality, parsePositiveInteger } from '../cardinality';

describe('cardinality extra', () => {
  it('buildIndexRecommendations handles combinations of columns correctly', () => {
    const columns = [
      { columnName: 'a', isSelected: true, distinctCount: '10' },
      { columnName: 'b', isSelected: true, distinctCount: '100' },
      { columnName: 'c', isSelected: true, distinctCount: '50' }
    ];
    const recs = buildIndexRecommendations({ tableName: 'tbl', columns, rowCount: 1000 });
    // Should test the permutations generated
    expect(recs.length).toBeGreaterThan(0);
    expect(recs[0].columns).toContain('b'); // max distinct should be first
  });

  it('buildIndexRecommendations handles skip cases (0 ratio or negative distinct count if valid)', () => {
    const columns = [
      { columnName: 'a', isSelected: true, distinctCount: '0' },
      { columnName: 'b', isSelected: true, distinctCount: '-10' },
    ];
    const recs = buildIndexRecommendations({ tableName: 'tbl', columns, rowCount: 1000 });
    expect(recs).toBeDefined();
    // 0 and -10 distinctCount evaluate to null distinct values which skip index recommendations.
    expect(recs).toEqual([]);
  });

  it('classifyCardinality considers threshold', () => {
     expect(classifyCardinality(0.01)).toBe('skip');
     expect(classifyCardinality(0.06)).toBe('consider');
     expect(classifyCardinality(0.20)).toBe('recommended');
  });

  it('buildIndexRecommendations combinations logic', () => {
     const columns = [
      { columnName: 'a', isSelected: true, distinctCount: '20' },
      { columnName: 'b', isSelected: true, distinctCount: '10' },
    ];
    const recs = buildIndexRecommendations({ tableName: 'tbl', columns, rowCount: 100 });
    // 'a' has ratio 0.20 => recommended
    // 'b' has ratio 0.10 => consider
    // It should generate an index for just 'a', and one for 'a, b'
    expect(recs.map(r => r.columns.join(','))).toContain('a');
    expect(recs.map(r => r.columns.join(','))).toContain('a,b');
  });

  it('parsePositiveInteger correctly handles inputs', () => {
     expect(parsePositiveInteger('10')).toBe(10);
     expect(parsePositiveInteger('0')).toBeNull();
     expect(parsePositiveInteger('-5')).toBeNull();
     expect(parsePositiveInteger('abc')).toBeNull();
     expect(parsePositiveInteger('1.5')).toBeNull();
  });
});
