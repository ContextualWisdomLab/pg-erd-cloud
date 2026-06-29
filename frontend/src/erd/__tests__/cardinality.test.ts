import { describe, it, expect } from 'vitest';
import { calculateCardinalityRatio, classifyCardinality, buildIndexName, parsePositiveInteger, buildIndexRecommendations } from '../cardinality';

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

describe('buildIndexName', () => {
  it('should build proper index names', () => {
    expect(buildIndexName('public.users', ['id'])).toBe('idx_users_id');
    expect(buildIndexName('users', ['id', 'email'])).toBe('idx_users_id_email');
    expect(buildIndexName('complex_table_name', ['col1', 'col2'])).toBe('idx_complex_table_name_col1_col2');
  });

  it('should sanitize identifiers', () => {
    expect(buildIndexName('my"table', ['col!1'])).toBe('idx_mytable_col_1');
    expect(buildIndexName('public.my-table', ['col-1'])).toBe('idx_my_table_col_1');
  });

  it('should fall back to col if empty', () => {
    expect(buildIndexName('public.table', [''])).toBe('idx_table_col');
  });

  it('should slice to MAX_INDEX_NAME_LENGTH (63)', () => {
    const veryLongTableName = 'a_very_long_table_name_that_exceeds_the_limit_of_characters_in_postgres';
    const name = buildIndexName(veryLongTableName, ['col1']);
    expect(name.length).toBeLessThanOrEqual(63);
    expect(name).toBe('idx_a_very_long_table_name_that_exceeds_the_limit_of_characters'.slice(0, 63));
  });
});

describe('parsePositiveInteger', () => {
  it('returns number for positive integer string', () => {
    expect(parsePositiveInteger('100')).toBe(100);
    expect(parsePositiveInteger('1')).toBe(1);
  });

  it('returns null for zero, negative, or non-integer', () => {
    expect(parsePositiveInteger('0')).toBe(null);
    expect(parsePositiveInteger('-10')).toBe(null);
    expect(parsePositiveInteger('1.5')).toBe(null);
    expect(parsePositiveInteger('abc')).toBe(null);
    expect(parsePositiveInteger('')).toBe(null);
  });
});

describe('buildIndexRecommendations', () => {
  it('returns empty array if rowCount is null or <= 0', () => {
    expect(buildIndexRecommendations({ tableName: 'users', rowCount: null, columns: [] })).toEqual([]);
    expect(buildIndexRecommendations({ tableName: 'users', rowCount: 0, columns: [] })).toEqual([]);
    expect(buildIndexRecommendations({ tableName: 'users', rowCount: -10, columns: [] })).toEqual([]);
  });

  it('builds recommendations for single selected column', () => {
    const recs = buildIndexRecommendations({
      tableName: 'users',
      rowCount: 1000,
      columns: [
        { columnName: 'id', isSelected: true, distinctCount: 1000 },
        { columnName: 'status', isSelected: false, distinctCount: 3 }
      ]
    });

    expect(recs).toHaveLength(1);
    expect(recs[0].index_name).toBe('idx_users_id');
    expect(recs[0].columns).toEqual(['id']);
    expect(recs[0].strength).toBe('recommended'); // 1000/1000 = 1.0
  });

  it('handles distinctCount exceeding rowCount', () => {
    const recs = buildIndexRecommendations({
      tableName: 'users',
      rowCount: 100,
      columns: [
        { columnName: 'id', isSelected: true, distinctCount: 1000 }
      ]
    });

    expect(recs[0].estimated_distinct).toBe(100); // capped at rowCount
    expect(recs[0].cardinality_ratio).toBe(1);
  });

  it('builds combined recommendation for multiple columns and sorts them', () => {
    const recs = buildIndexRecommendations({
      tableName: 'users',
      rowCount: 1000,
      columns: [
        { columnName: 'status', isSelected: true, distinctCount: 5 },     // 5/1000 = 0.005 -> skip
        { columnName: 'role_id', isSelected: true, distinctCount: 100 }    // 100/1000 = 0.1 -> consider
      ]
    });

    expect(recs).toHaveLength(3);

    // Sort order should be: recommended > consider > skip, then by ratio desc
    // Combined distinct = min(1000, 5 * 100) = 500 (ratio 0.5) -> recommended
    expect(recs[0].columns).toEqual(['status', 'role_id']);
    expect(recs[0].strength).toBe('recommended');
    expect(recs[0].cardinality_ratio).toBe(0.5);

    expect(recs[1].columns).toEqual(['role_id']);
    expect(recs[1].strength).toBe('consider');

    expect(recs[2].columns).toEqual(['status']);
    expect(recs[2].strength).toBe('skip');
  });

  it('ignores invalid distinctCount', () => {
    const recs = buildIndexRecommendations({
      tableName: 'users',
      rowCount: 1000,
      columns: [
        { columnName: 'invalid1', isSelected: true, distinctCount: null },
        { columnName: 'invalid2', isSelected: true, distinctCount: 0 },
        { columnName: 'valid', isSelected: true, distinctCount: 100 }
      ]
    });

    expect(recs).toHaveLength(1);
    expect(recs[0].columns).toEqual(['valid']);
  });

  it('sorts by cardinality ratio when strengths are equal', () => {
    const recs = buildIndexRecommendations({
      tableName: 'users',
      rowCount: 1000,
      columns: [
        { columnName: 'col1', isSelected: true, distinctCount: 800 },
        { columnName: 'col2', isSelected: true, distinctCount: 900 }
      ]
    });

    expect(recs[1].columns).toEqual(['col2']);
    expect(recs[2].columns).toEqual(['col1']);
  });
});
