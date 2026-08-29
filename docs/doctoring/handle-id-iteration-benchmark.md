# ERD handle-ID iteration benchmark doctoring

## Decision

`sanitizeHandleId` keeps the existing code-point encoding contract while replacing
`Array.from(...).join('-')` with a single `for...of` pass and incremental string
construction. The empty-input sentinel (`c-empty`) and the `src-`/`tgt-` prefixes
remain unchanged.

ECMAScript `for...of` string iteration and `Array.from` both consume the string
iterator, so both paths observe Unicode code points rather than individual UTF-16
code units. The regression suite fixes ASCII, Hangul, astral emoji, combining
marks, zero-width-joiner sequences, mixed case, punctuation, the maximum Unicode
scalar, and a lone surrogate against the predecessor implementation.

## Benchmark method

The tracked harness:

- warms both implementations;
- executes 50 deterministic counterbalanced pairs (`optimized→original`, then
  `original→optimized`);
- runs the same eight-string corpus for 10,000 iterations per sample;
- records the pair index, execution order, elapsed duration, checksum, and the
  diagnostic `process.memoryUsage().heapUsed` delta;
- computes even-length medians by averaging the two central values;
- fails if the paired output checksums differ; and
- writes the complete ordered evidence to
  `frontend/docs/benchmark_results/handleUtils.json`.

The committed artifact was produced on Linux x64 with Node.js 22.16.0 because the
local execution environment did not contain the repository-required Node 26
runtime. It observed a median paired elapsed-time improvement recorded in the
artifact, but it is supporting evidence only. Node 26 type stripping is stable,
and the unchanged exact PR head must rerun the benchmark and the complete
frontend tests/typecheck/coverage/build before a release claim.

`heapUsedAfter - heapUsedBefore` is retained only as a diagnostic V8 heap snapshot
difference. Node.js documents `heapUsed` as current V8 memory usage; the delta is
not allocated bytes, garbage-collection count, pause duration, or whole-browser
memory reduction. No frame-rate or end-to-end rendering improvement is claimed.

## Monitoring and rollback

Monitor diagram load time, renderer long tasks, and handle/edge mismatch errors on
large schemas. Roll back the production file and its benchmark evidence together
if any stable identifier differs or Node 26 exact-head evidence reverses the
performance direction. Do not retain a benchmark-only package dependency.

## References

Ecma International. (2026, July 1). *Ecma International approves new standards:
ECMA-262 17th edition—ECMAScript 2026 language specification*.
https://ecma-international.org/news/ecma-international-approves-new-standards-14/

Georges, A., Buytaert, D., & Eeckhout, L. (2007). Statistically rigorous Java
performance evaluation. *ACM SIGPLAN Notices, 42*(10), 57–76.
https://doi.org/10.1145/1297027.1297033

Node.js contributors. (2026). *Modules: TypeScript—Node.js v26 documentation*.
https://nodejs.org/dist/latest/docs/api/typescript.html

Node.js contributors. (2026). *Process: `process.memoryUsage()`—Node.js v26
documentation*. https://nodejs.org/api/process.html
