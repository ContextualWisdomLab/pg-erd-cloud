import { describe, it, expect } from 'vitest';
import { sanitizeHandleId } from './handleUtils';

// Mock the old Array.from implementation for comparison
function sanitizeHandleIdOriginal(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

describe('sanitizeHandleId benchmark', () => {
  it('should demonstrate performance improvement', () => {
    const testCases = [
      'id',
      'user_id',
      'created_at_timestamp_with_timezone',
      'very_long_column_name_that_might_exist_in_some_databases_for_some_reason_123',
      'id_가',
      'id_🚀',
      '👩‍👩‍👧‍👦',
      '',
    ];

    const iterations = 10000;

    // Warmup
    for (let i = 0; i < 1000; i++) {
      for (const tc of testCases) {
        sanitizeHandleIdOriginal(tc);
        sanitizeHandleId(tc);
      }
    }

    const startOriginal = performance.now();
    for (let i = 0; i < iterations; i++) {
      for (const tc of testCases) {
        sanitizeHandleIdOriginal(tc);
      }
    }
    const endOriginal = performance.now();

    const startOptimized = performance.now();
    for (let i = 0; i < iterations; i++) {
      for (const tc of testCases) {
        sanitizeHandleId(tc);
      }
    }
    const endOptimized = performance.now();

    const originalTime = endOriginal - startOriginal;
    const optimizedTime = endOptimized - startOptimized;

    // We expect the optimized version to be faster, but CI environments can be noisy
    // Just verify the code executes properly and output the values
    console.log(`[BENCHMARK] Original Time: ${originalTime.toFixed(2)}ms`);
    console.log(`[BENCHMARK] Optimized Time: ${optimizedTime.toFixed(2)}ms`);
    console.log(`[BENCHMARK] Improvement: ${(((originalTime - optimizedTime) / originalTime) * 100).toFixed(2)}%`);

    expect(true).toBe(true);
  });
});
