# Diagram-list readiness and fake-timer test isolation

## Decision

The four async orchestration tests in `frontend/src/App.coverage.test.tsx`
that open a diagram and then advance timers now await the diagram `열기`
controls under real timers before calling `vi.useFakeTimers()`. The readiness
wait is scoped to the diagram-list render. Polling, undo, terminal-refresh,
and error assertions are unchanged.

## Why

`renderReadyApp()` waits for the dashboard heading. The diagram list is
populated by `listSnapshots(selectedProjectId)`, whose resolution schedules a
state update on that same dashboard render. When `vi.useFakeTimers()` runs
before that update commits, the following synchronous
`getAllByRole('button', { name: '열기' })` can observe a tree with no diagram
rows and fail at the click instead of at the behavior under test.

The asynchronous boundary is the diagram-list render, not a mocked request or
a stale-state leak: `listSnapshots` resolves the seeded snapshot list, and the
test only needs to observe that resolution before freezing time. Awaiting the
button under real timers and enabling fake timers afterwards keeps the wait on
the same boundary the effect owns.

## Invariants

- Fake timers are enabled only after at least one diagram row is visible.
- The four tests keep their existing layout, polling, undo, terminal-refresh,
  and error assertions.
- No production, dependency, lockfile, or performance behavior changes.

## Verification

Reproduced and verified under the repository-required Node 26 runtime
(`mise x node@26.8.2`, engines `>=26 <27`) in an isolated worktree on
protected `main@8dc746920c12988f082e914879d95e13c9693535`:

- RED: 20 repeated full-file runs of `src/App.coverage.test.tsx` failed 3
  times on the unmodified tree (two failures in the target fake-timer tests,
  one adjacent diagram-list readiness failure in
  `navigates dashboard, project, and diagram states...`).
- GREEN: 20 repeated focused runs of the four repaired tests passed 20/20 on
  the repaired head.
- 20 repeated full-file runs on the repaired head passed 19/20. The single
  remaining failure is a `Test timed out in 5000ms` in
  `covers guarded editor actions, navigation callbacks, and form selectors`,
  which also fails 2/20 focused repetitions on the unmodified base. That
  flake is outside the four-test fake-timer scope and is tracked separately.

Repository CI remains authoritative for the exact head: complete frontend
test, type check, coverage, and production build.

## Operational monitoring and rollback

Monitor repeated-run failures for this file and CI frontend job history. Roll
back by restoring the immediate fake-timer switch only if a verified
regression requires it; doing so reopens the documented readiness race and
therefore requires a replacement isolation design and regression evidence.

## References

Testing Library. (n.d.). *Async methods*. Retrieved September 11, 2026, from
https://testing-library.com/docs/dom-testing-library/api-async/

Vitest. (n.d.). *vi.useFakeTimers*. Retrieved September 11, 2026, from
https://vitest.dev/api/vi.html#vi-usefaketimers
