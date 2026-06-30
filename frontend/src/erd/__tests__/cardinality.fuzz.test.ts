import fc from 'fast-check';
import { describe, expect, it } from 'vitest';

import {
  buildIndexName,
  calculateCardinalityRatio,
  classifyCardinality,
  parsePositiveInteger,
} from '../cardinality';

describe('cardinality fuzz properties', () => {
  it('keeps calculated ratios finite and clamped', () => {
    fc.assert(
      fc.property(
        fc.double({ noDefaultInfinity: true, noNaN: true }),
        fc.double({ noDefaultInfinity: true, noNaN: true }),
        (rowCount, distinctCount) => {
          const ratio = calculateCardinalityRatio(rowCount, distinctCount);

          expect(Number.isFinite(ratio)).toBe(true);
          expect(ratio).toBeGreaterThanOrEqual(0);
          expect(ratio).toBeLessThanOrEqual(1);
        },
      ),
    );
  });

  it('classifies every clamped ratio into a known strength', () => {
    fc.assert(
      fc.property(fc.float({ min: 0, max: 1, noNaN: true }), (ratio) => {
        expect(['recommended', 'consider', 'skip']).toContain(
          classifyCardinality(ratio),
        );
      }),
    );
  });

  it('builds PostgreSQL-safe bounded index names from arbitrary identifiers', () => {
    fc.assert(
      fc.property(
        fc.string(),
        fc.array(fc.string(), { maxLength: 5 }),
        (tableName, columns) => {
          const indexName = buildIndexName(tableName, columns);

          expect(indexName).toMatch(/^idx_[a-z0-9_]+$/);
          expect(indexName.length).toBeLessThanOrEqual(63);
        },
      ),
    );
  });

  it('parses only positive integer strings', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: Number.MAX_SAFE_INTEGER }), (value) => {
        expect(parsePositiveInteger(String(value))).toBe(value);
      }),
    );
  });
});
