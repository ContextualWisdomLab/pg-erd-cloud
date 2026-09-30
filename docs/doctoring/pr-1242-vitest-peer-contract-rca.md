# PR #1242 Vitest peer dependency RCA

Status: Proposed source repair; exact-head hosted Checks and independent review remain mandatory.

## Incident evidence

`ContextualWisdomLab/pg-erd-cloud#1242@cb1be77b2209dcf1919a94d62efe2393c7c32940`
failed frontend CI run `36668767330`, job `109739048510`, during `npm ci`.
The resolver reported `ERESOLVE`: `vitest@5.0.2` had been selected while
`@vitest/coverage-v8@4.1.10` required the exact peer `vitest@4.1.10`.

The grouped dependency update changed the direct Vitest runtime to major 5 but
did not move its coverage provider. This is a manifest/lock atomicity defect,
not a runner race. `--force`, `--legacy-peer-deps`, a skipped install, or a gate
change would hide the invalid graph and are rejected.

## Test-first repair

1. RED: the new standard-library contract read `frontend/package.json` and
   `frontend/package-lock.json` and failed with `'^5.0.2' != '^4.1.9'`.
2. First hypothesis: move the entire Vitest family to 5.0.2. Installation then
   succeeded, but TypeScript exposed a second incompatibility:
   `@testing-library/jest-dom`, including current `7.0.1`, augments
   `Assertion<T>` while Vitest 5 declares `Assertion<R, T>`.
3. Selected repair: retain the working Vitest 4 release line, resolve the
   runtime and V8 coverage provider together, and keep a lockfile contract that
   proves the installed versions and coverage peer are identical.
4. Rejected alternative: add a repository-owned type shim or enable
   `skipLibCheck`. That would duplicate upstream type authority or conceal the
   incompatibility.

Vitest 5 remains a separate Proposed migration. Its admission requires an
upstream-compatible DOM matcher release or an evidence-backed removal of that
integration, followed by the full frontend typecheck, test, coverage, build,
security, and exact-head hosted gates.

## Local acceptance evidence

All commands used Node `26.10.0`:

- clean `npm ci`: success;
- full npm audit at Moderate+: 0 vulnerabilities after resolving `nanoid` to
  3.3.19 and `undici` to 8.11.2 within their existing parent ranges;
- frontend typecheck: success;
- 28 test files / 201 tests: success;
- V8 coverage: 1,518/1,521 statements and 1,143/1,151 branches; this pre-existing
  non-100% product gap is measured, not suppressed;
- production build: success;
- dependency contract: success under the Python standard library and remains
  discoverable by the repository pytest suite.
- backend mypy: 68 source files, no issues;
- backend pytest with inherited proxy variables removed: 380 passed, 1 skipped.
  The suite still emits the pre-existing Starlette `httpx` deprecation warning;
  it is recorded as a separate migration gap rather than suppressed here.

Hosted exact-head CI, Semgrep, Security Scan, CodeQL, and independent review
remain the merge authority.
