import { sanitizeHandleId } from '../src/erd/handleUtils.js';
import { performance } from 'node:perf_hooks';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function sanitizeHandleIdOriginal(columnName: string): string {
  const encoded = Array.from(columnName, (char) => {
    return char.codePointAt(0)!.toString(16).padStart(4, '0')
  }).join('-')

  return `c-${encoded || 'empty'}`
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

const iterationsPerSample = 10000;
const numSamples = 50; // Use an even number for perfectly balanced A/B vs B/A runs

function failClosed(msg: string) {
  console.error(`Benchmark failed: ${msg}`);
  process.exit(1);
}

function runSample(fn: (str: string) => string) {
  global.gc!();
  const startHeap = process.memoryUsage().heapUsed;
  const start = performance.now();
  for (let i = 0; i < iterationsPerSample; i++) {
    for (const tc of testCases) {
      fn(tc);
    }
  }
  const end = performance.now();
  // We record the raw heap delta without clamping to 0.
  // For precise allocation profiling, Node's built-in hooks or V8 isolate snapshots
  // are necessary, but forcing a full GC immediately prior helps stabilize transient heap deltas.
  const endHeap = process.memoryUsage().heapUsed;

  return { time: end - start, heapDelta: endHeap - startHeap };
}

/** Return mean, correctly interpolated median, and sorted raw samples. */
export function calculateStats(samples: number[]) {
  const sorted = [...samples].sort((a, b) => a - b);
  const sum = sorted.reduce((a, b) => a + b, 0);
  const mean = sum / sorted.length;
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
  return { mean, median, raw: sorted };
}

function runBenchmark() {
  if (!global.gc) {
    failClosed('--expose-gc is required but global.gc is unavailable. Run via: pnpm run benchmark:handleUtils');
  }

  console.log(`Platform: ${process.platform} ${process.arch}`);
  console.log(`Node.js Version: ${process.version}`);
  console.log(`V8 Version: ${process.versions?.v8 || 'unknown'}`);
  console.log(`Corpus: ${testCases.length} strings of varying length and charset`);
  console.log(`Iterations per sample: ${iterationsPerSample}`);
  console.log(`Number of samples: ${numSamples}`);
  console.log('---');

  // Warmup
  for (let i = 0; i < 1000; i++) {
    for (const tc of testCases) {
      sanitizeHandleIdOriginal(tc);
      sanitizeHandleId(tc);
    }
  }

  const originalSamplesTime: number[] = [];
  const optimizedSamplesTime: number[] = [];
  const originalSamplesMem: number[] = [];
  const optimizedSamplesMem: number[] = [];

  // Deterministic Counterbalanced Ordering (A B, B A)
  for (let s = 0; s < numSamples; s++) {
    const runOptimizedFirst = (s % 2 === 0);

    if (runOptimizedFirst) {
      const optResult = runSample(sanitizeHandleId);
      const origResult = runSample(sanitizeHandleIdOriginal);
      optimizedSamplesTime.push(optResult.time);
      optimizedSamplesMem.push(optResult.heapDelta);
      originalSamplesTime.push(origResult.time);
      originalSamplesMem.push(origResult.heapDelta);
    } else {
      const origResult = runSample(sanitizeHandleIdOriginal);
      const optResult = runSample(sanitizeHandleId);
      originalSamplesTime.push(origResult.time);
      originalSamplesMem.push(origResult.heapDelta);
      optimizedSamplesTime.push(optResult.time);
      optimizedSamplesMem.push(optResult.heapDelta);
    }
  }

  const origTimeStats = calculateStats(originalSamplesTime);
  const optTimeStats = calculateStats(optimizedSamplesTime);
  const origMemStats = calculateStats(originalSamplesMem);
  const optMemStats = calculateStats(optimizedSamplesMem);

  console.log('--- Raw Results ---');
  console.log(`Original Time (mean): ${origTimeStats.mean.toFixed(2)}ms`);
  console.log(`Original Time (median): ${origTimeStats.median.toFixed(2)}ms`);
  console.log(`Optimized Time (mean): ${optTimeStats.mean.toFixed(2)}ms`);
  console.log(`Optimized Time (median): ${optTimeStats.median.toFixed(2)}ms`);
  console.log('---');
  console.log(`Original Heap Delta (mean): ${(origMemStats.mean / 1024).toFixed(2)} KB`);
  console.log(`Optimized Heap Delta (mean): ${(optMemStats.mean / 1024).toFixed(2)} KB`);
  console.log('---');
  console.log(`Time Improvement (median): ${(((origTimeStats.median - optTimeStats.median) / origTimeStats.median) * 100).toFixed(2)}%`);
  console.log(`Heap Delta Reduction (mean): ${(((origMemStats.mean - optMemStats.mean) / origMemStats.mean) * 100).toFixed(2)}%`);

  // Save exact raw output
  const resultsObj = {
      metadata: {
          platform: `${process.platform} ${process.arch}`,
          node: process.version,
          v8: process.versions?.v8 || 'unknown',
          iterationsPerSample,
          numSamples
      },
      timeStats: {
          original: origTimeStats,
          optimized: optTimeStats
      },
      heapDeltaStats: {
          original: origMemStats,
          optimized: optMemStats
      }
  };

  const resultsPath = path.join(__dirname, '..', 'docs', 'benchmark_results', 'handleUtils.json');
  fs.mkdirSync(path.dirname(resultsPath), { recursive: true });
  fs.writeFileSync(resultsPath, JSON.stringify(resultsObj, null, 2), 'utf-8');
  console.log(`\nRaw paired samples and statistics written to ${resultsPath}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  runBenchmark();
}
