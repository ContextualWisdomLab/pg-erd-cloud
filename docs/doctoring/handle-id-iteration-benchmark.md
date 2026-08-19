# ERD handle-ID iteration benchmark

## Status

Implemented as a behavior-preserving optimization with a separately invocable
microbenchmark. Exact-head CI on the repository-supported Node 26 runtime
remains the release authority.

## Product boundary

`sanitizeHandleId` converts each Unicode code point in a column name to the
existing hexadecimal handle representation. The optimized path iterates the
string directly and appends encoded segments without first materializing the
intermediate array that `Array.from(...).join(...)` requires. Empty strings and
all encoded output remain byte-for-byte compatible with the predecessor.

The ECMAScript specification defines `Array.from` as creating a new array from
an iterable and defines string iteration in Unicode-code-point terms. The
implementation therefore removes one specified intermediate container while
preserving the same Unicode scalar sequence. This is a local implementation
fact, not a claim that every `for...of` rewrite is faster.

## Measurement contract

The checked-in harness:

- warms both implementations before timing;
- runs 50 paired samples;
- alternates deterministic `optimized → original` and `original → optimized`
  order to balance order effects;
- preserves each pair index, execution order, elapsed duration, and diagnostic
  heap delta in raw output;
- calculates the median of an even-length sample as the mean of its two middle
  values;
- reports elapsed-time improvement for each pair instead of comparing two
  independently sorted sample arrays;
- labels `heapUsedAfter - heapUsedBefore` as a V8 heap-use delta only.

`process.memoryUsage().heapUsed` describes V8 heap use at the observation point;
it is not an allocation counter. The benchmark therefore does not convert that
net delta into allocated bytes, garbage-collection count, or pause time.
Allocation attribution would require a dedicated V8 allocation profiler or
heap-sampling experiment.

Georges, Buytaert, and Eeckhout's statistically rigorous managed-runtime
benchmark guidance motivates warm-up, repeated observations, explicit
nondeterminism handling, and reporting distributions rather than one timing.
The harness applies those principles at the bounded microbenchmark level; it
does not substitute for a browser-level rendering benchmark.

## Evidence interpretation

The committed raw artifact records one supporting Darwin arm64 run under Node
24.16.0. It observed a paired median elapsed-time improvement of approximately
41.80% for the fixed eight-string corpus and 10,000 iterations per sample. This
run validates the corrected evidence shape and shows the optimization is worth
retesting, but it is not release evidence because the repository supports Node
26.

The exact-head Node 26 benchmark, frontend type check, complete test suite,
coverage run, and production build are authoritative. Quantitative claims must
name the runtime, V8 version, corpus, pair count, and iteration count and must
not be generalized to whole-application frame rate or memory consumption.

## Reproduction

```bash
cd frontend
npm ci
npm run benchmark:handleUtils
```

Node 26 executes erasable TypeScript syntax through its stable built-in type
stripping, so the benchmark requires no additional runtime dependency. The
`.ts` extension in the relative import is intentional and required by Node's
TypeScript module-resolution contract.

## Monitoring and rollback

Monitor exact handle-string regressions and the paired elapsed-time distribution
on supported Node/V8 upgrades. Revert the production loop and benchmark evidence
together if output parity changes or a supported runtime no longer demonstrates
a stable benefit. Never preserve a performance claim after its raw evidence or
runtime contract becomes stale.

## References

Ecma International. (2026). *ECMAScript® 2026 language specification*
(ECMA-262, 17th ed.). https://262.ecma-international.org/17.0/

Georges, A., Buytaert, D., & Eeckhout, L. (2007). Statistically rigorous Java
performance evaluation. *ACM SIGPLAN Notices, 42*(10), 57–76.
https://doi.org/10.1145/1297027.1297033

OpenJS Foundation. (2026). *Modules: TypeScript—Node.js v26 documentation*.
https://nodejs.org/docs/latest-v26.x/api/typescript.html

OpenJS Foundation. (2026). *Process—Node.js v26 documentation*.
https://nodejs.org/docs/latest-v26.x/api/process.html#processmemoryusage

V8 Project. (2017, November 29). *Orinoco: Young generation garbage
collection*. https://v8.dev/blog/orinoco-parallel-scavenger
