import { describe, bench } from 'vitest';
import { sanitizeHandleId as optimizedSanitizeHandleId } from './handleUtils';

// Reference implementation (prior scalar-map contract)
function referenceSanitizeHandleId(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
}

const inputCorpus = [
    "user_id",
    "created_at",
    "id",
    "an_extremely_long_column_name_that_should_test_the_bounds_of_performance_for_this_specific_function_call",
    "이름",
    "👨‍👩‍👧‍👦", // surrogate pairs and ZWJ
    "",
    "e\u0301",
    "mixed_가_bmp_🚀_nonbmp"
];

describe('sanitizeHandleId', () => {
    bench('reference implementation (Array.from)', () => {
        for (const input of inputCorpus) {
            referenceSanitizeHandleId(input);
        }
    });

    bench('optimized implementation (for loop)', () => {
        for (const input of inputCorpus) {
            optimizedSanitizeHandleId(input);
        }
    });
});
