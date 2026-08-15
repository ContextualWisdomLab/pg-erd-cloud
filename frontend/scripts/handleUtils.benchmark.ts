import { sanitizeHandleId } from '../src/erd/handleUtils';

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
const numSamples = 50;

function runSample(fn: (str: string) => string) {
  if (global.gc) {
    global.gc();
  }
  const startMem = process.memoryUsage().heapUsed;
  const start = performance.now();
  for (let i = 0; i < iterationsPerSample; i++) {
    for (const tc of testCases) {
      fn(tc);
    }
  }
  const end = performance.now();
  const endMem = process.memoryUsage().heapUsed;
  return { time: end - start, memoryAllocated: Math.max(0, endMem - startMem) };
}

function calculateStats(samples: number[]) {
  const sorted = [...samples].sort((a, b) => a - b);
  const sum = sorted.reduce((a, b) => a + b, 0);
  const mean = sum / sorted.length;
  const median = sorted[Math.floor(sorted.length / 2)];
  return { mean, median, raw: sorted };
}

function runBenchmark() {
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

  // Randomize order
  for (let s = 0; s < numSamples; s++) {
    const runOptimizedFirst = Math.random() > 0.5;

    if (runOptimizedFirst) {
      const optResult = runSample(sanitizeHandleId);
      const origResult = runSample(sanitizeHandleIdOriginal);
      optimizedSamplesTime.push(optResult.time);
      optimizedSamplesMem.push(optResult.memoryAllocated);
      originalSamplesTime.push(origResult.time);
      originalSamplesMem.push(origResult.memoryAllocated);
    } else {
      const origResult = runSample(sanitizeHandleIdOriginal);
      const optResult = runSample(sanitizeHandleId);
      originalSamplesTime.push(origResult.time);
      originalSamplesMem.push(origResult.memoryAllocated);
      optimizedSamplesTime.push(optResult.time);
      optimizedSamplesMem.push(optResult.memoryAllocated);
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
  console.log(`Original Memory Allocated (mean): ${(origMemStats.mean / 1024).toFixed(2)} KB`);
  console.log(`Optimized Memory Allocated (mean): ${(optMemStats.mean / 1024).toFixed(2)} KB`);
  console.log('---');
  console.log(`Time Improvement (median): ${(((origTimeStats.median - optTimeStats.median) / origTimeStats.median) * 100).toFixed(2)}%`);
  console.log(`Memory Improvement (mean): ${(((origMemStats.mean - optMemStats.mean) / origMemStats.mean) * 100).toFixed(2)}%`);
}

runBenchmark();
