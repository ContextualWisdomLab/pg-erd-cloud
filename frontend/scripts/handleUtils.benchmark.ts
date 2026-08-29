import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { performance } from 'node:perf_hooks'

import { sanitizeHandleId } from '../src/erd/handleUtils.ts'

type HandleEncoder = (columnName: string) => string

type SampleResult = {
  elapsedMilliseconds: number
  heapUsedDeltaBytes: number
  checksum: number
}

function sanitizeHandleIdOriginal(columnName: string): string {
  const encoded = Array.from(columnName, (character) =>
    character.codePointAt(0)!.toString(16).padStart(4, '0'),
  ).join('-')
  return `c-${encoded || 'empty'}`
}

const corpus = [
  'id',
  'user_id',
  'created_at_timestamp_with_timezone',
  'very_long_column_name_that_might_exist_in_some_databases_for_some_reason_123',
  'id_가',
  'id_🚀',
  '👩‍👩‍👧‍👦',
  '',
] as const
const iterationsPerSample = 10_000
const pairCount = 50

function mean(values: readonly number[]): number {
  if (values.length === 0) throw new Error('mean requires at least one value')
  return values.reduce((total, value) => total + value, 0) / values.length
}

function median(values: readonly number[]): number {
  if (values.length === 0) throw new Error('median requires at least one value')
  const ordered = [...values].sort((left, right) => left - right)
  const middle = Math.floor(ordered.length / 2)
  return ordered.length % 2 === 0
    ? (ordered[middle - 1] + ordered[middle]) / 2
    : ordered[middle]
}

function assertHarnessContract(): void {
  if (median([1, 2, 3, 4]) !== 2.5 || median([1, 2, 3]) !== 2) {
    throw new Error('median contract failed')
  }
  const orders = Array.from({ length: 4 }, (_, pairIndex) =>
    pairIndex % 2 === 0 ? 'optimized-first' : 'original-first',
  )
  if (orders.join(',') !== 'optimized-first,original-first,optimized-first,original-first') {
    throw new Error('counterbalanced order contract failed')
  }
}

function runSample(operation: HandleEncoder): SampleResult {
  global.gc!()
  const heapUsedBeforeBytes = process.memoryUsage().heapUsed
  const startedAt = performance.now()
  let checksum = 0
  for (let iteration = 0; iteration < iterationsPerSample; iteration += 1) {
    for (const value of corpus) checksum += operation(value).length
  }
  const elapsedMilliseconds = performance.now() - startedAt
  const heapUsedAfterBytes = process.memoryUsage().heapUsed
  return {
    elapsedMilliseconds,
    heapUsedDeltaBytes: heapUsedAfterBytes - heapUsedBeforeBytes,
    checksum,
  }
}

function runBenchmark(): void {
  if (typeof global.gc !== 'function') {
    throw new Error('Run the benchmark with --expose-gc')
  }
  assertHarnessContract()

  for (let iteration = 0; iteration < 1_000; iteration += 1) {
    for (const value of corpus) {
      sanitizeHandleIdOriginal(value)
      sanitizeHandleId(value)
    }
  }

  const pairs = []
  for (let pairIndex = 0; pairIndex < pairCount; pairIndex += 1) {
    const order = pairIndex % 2 === 0 ? 'optimized-first' : 'original-first'
    let original: SampleResult
    let optimized: SampleResult
    if (order === 'optimized-first') {
      optimized = runSample(sanitizeHandleId)
      original = runSample(sanitizeHandleIdOriginal)
    } else {
      original = runSample(sanitizeHandleIdOriginal)
      optimized = runSample(sanitizeHandleId)
    }
    if (original.checksum !== optimized.checksum) {
      throw new Error(`output checksum mismatch in pair ${pairIndex}`)
    }
    pairs.push({ pairIndex, order, original, optimized })
  }

  const originalElapsed = pairs.map((pair) => pair.original.elapsedMilliseconds)
  const optimizedElapsed = pairs.map((pair) => pair.optimized.elapsedMilliseconds)
  const pairedImprovement = pairs.map(
    (pair) =>
      ((pair.original.elapsedMilliseconds - pair.optimized.elapsedMilliseconds) /
        pair.original.elapsedMilliseconds) *
      100,
  )
  const artifact = {
    schemaVersion: 1,
    metadata: {
      platform: process.platform,
      architecture: process.arch,
      nodeVersion: process.version,
      v8Version: process.versions.v8,
      corpus: [...corpus],
      iterationsPerSample,
      pairCount,
      orderPolicy: 'counterbalanced-ab-ba',
    },
    interpretation: {
      heapUsedDeltaBytes:
        'Diagnostic process.memoryUsage().heapUsed difference; not allocated bytes, GC count, or pause time.',
    },
    summary: {
      originalElapsedMilliseconds: {
        mean: mean(originalElapsed),
        median: median(originalElapsed),
      },
      optimizedElapsedMilliseconds: {
        mean: mean(optimizedElapsed),
        median: median(optimizedElapsed),
      },
      pairedImprovementPercent: {
        mean: mean(pairedImprovement),
        median: median(pairedImprovement),
      },
      originalHeapUsedDeltaBytesMean: mean(
        pairs.map((pair) => pair.original.heapUsedDeltaBytes),
      ),
      optimizedHeapUsedDeltaBytesMean: mean(
        pairs.map((pair) => pair.optimized.heapUsedDeltaBytes),
      ),
    },
    pairs,
  }
  const outputPath = resolve(
    dirname(fileURLToPath(import.meta.url)),
    '../docs/benchmark_results/handleUtils.json',
  )
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, `${JSON.stringify(artifact)}\n`, 'utf8')
  console.log(JSON.stringify(artifact.summary, null, 2))
  console.log(`Wrote ${outputPath}`)
}

const entryPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : ''
if (import.meta.url === entryPath) runBenchmark()
