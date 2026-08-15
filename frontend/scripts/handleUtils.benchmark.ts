import { performance } from 'node:perf_hooks';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { sanitizeHandleId } from '../src/erd/handleUtils.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

type BenchmarkFunction = (value: string) => string;
type ExecutionOrder = 'optimized_then_original' | 'original_then_optimized';

interface Measurement {
  elapsedMilliseconds: number;
  heapUsedDeltaBytes: number;
}

interface PairedSample {
  pairIndex: number;
  executionOrder: ExecutionOrder;
  original: Measurement;
  optimized: Measurement;
  elapsedImprovementPercent: number;
}

interface SummaryStatistics {
  mean: number;
  median: number;
}

function sanitizeHandleIdOriginal(columnName: string): string {
  const encoded = Array.from(columnName, (char) =>
    char.codePointAt(0)!.toString(16).padStart(4, '0'),
  ).join('-');

  return `c-${encoded || 'empty'}`;
}

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

const iterationsPerSample = 10_000;
const numberOfPairs = 50;

function failClosed(message: string): never {
  throw new Error(`Benchmark failed: ${message}`);
}

function forceGarbageCollection(): void {
  if (!global.gc) {
    failClosed(
      '--expose-gc is required but global.gc is unavailable. Run via: npm run benchmark:handleUtils',
    );
  }
  global.gc();
}

function runMeasurement(fn: BenchmarkFunction): Measurement {
  forceGarbageCollection();
  const heapUsedBefore = process.memoryUsage().heapUsed;
  const startedAt = performance.now();

  for (let iteration = 0; iteration < iterationsPerSample; iteration += 1) {
    for (const testCase of testCases) {
      fn(testCase);
    }
  }

  const elapsedMilliseconds = performance.now() - startedAt;
  const heapUsedAfter = process.memoryUsage().heapUsed;
  return {
    elapsedMilliseconds,
    heapUsedDeltaBytes: heapUsedAfter - heapUsedBefore,
  };
}

function median(values: readonly number[]): number {
  if (values.length === 0) {
    failClosed('cannot summarize an empty sample');
  }

  const sorted = [...values].sort((left, right) => left - right);
  const upperIndex = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) {
    return sorted[upperIndex];
  }
  return (sorted[upperIndex - 1] + sorted[upperIndex]) / 2;
}

function summarize(values: readonly number[]): SummaryStatistics {
  if (values.length === 0) {
    failClosed('cannot summarize an empty sample');
  }

  return {
    mean: values.reduce((total, value) => total + value, 0) / values.length,
    median: median(values),
  };
}

function runBenchmark(): void {
  for (let iteration = 0; iteration < 1_000; iteration += 1) {
    for (const testCase of testCases) {
      sanitizeHandleIdOriginal(testCase);
      sanitizeHandleId(testCase);
    }
  }

  const samples: PairedSample[] = [];
  for (let pairIndex = 0; pairIndex < numberOfPairs; pairIndex += 1) {
    const optimizedFirst = pairIndex % 2 === 0;
    const executionOrder: ExecutionOrder = optimizedFirst
      ? 'optimized_then_original'
      : 'original_then_optimized';

    const first = runMeasurement(
      optimizedFirst ? sanitizeHandleId : sanitizeHandleIdOriginal,
    );
    const second = runMeasurement(
      optimizedFirst ? sanitizeHandleIdOriginal : sanitizeHandleId,
    );
    const original = optimizedFirst ? second : first;
    const optimized = optimizedFirst ? first : second;

    samples.push({
      pairIndex,
      executionOrder,
      original,
      optimized,
      elapsedImprovementPercent:
        ((original.elapsedMilliseconds - optimized.elapsedMilliseconds) /
          original.elapsedMilliseconds) *
        100,
    });
  }

  const result = {
    metadata: {
      platform: `${process.platform} ${process.arch}`,
      node: process.version,
      v8: process.versions.v8,
      iterationsPerSample,
      numberOfPairs,
      corpusSize: testCases.length,
      ordering: 'deterministic counterbalanced AB/BA',
      rawEvidence: 'samples preserve pair and execution order',
      heapMetric:
        'heapUsed after minus heapUsed before each timed sample; diagnostic only, not allocated bytes',
    },
    samples,
    elapsedMilliseconds: {
      original: summarize(
        samples.map((sample) => sample.original.elapsedMilliseconds),
      ),
      optimized: summarize(
        samples.map((sample) => sample.optimized.elapsedMilliseconds),
      ),
      pairedImprovementPercent: summarize(
        samples.map((sample) => sample.elapsedImprovementPercent),
      ),
    },
    heapUsedDeltaBytes: {
      original: summarize(
        samples.map((sample) => sample.original.heapUsedDeltaBytes),
      ),
      optimized: summarize(
        samples.map((sample) => sample.optimized.heapUsedDeltaBytes),
      ),
    },
  };

  const resultsPath = path.join(
    __dirname,
    '..',
    'docs',
    'benchmark_results',
    'handleUtils.json',
  );
  fs.mkdirSync(path.dirname(resultsPath), { recursive: true });
  fs.writeFileSync(resultsPath, `${JSON.stringify(result, null, 2)}\n`, 'utf-8');

  console.log(
    JSON.stringify(
      {
        resultsPath,
        originalMedianMilliseconds:
          result.elapsedMilliseconds.original.median,
        optimizedMedianMilliseconds:
          result.elapsedMilliseconds.optimized.median,
        pairedMedianImprovementPercent:
          result.elapsedMilliseconds.pairedImprovementPercent.median,
      },
      null,
      2,
    ),
  );
}

runBenchmark();
