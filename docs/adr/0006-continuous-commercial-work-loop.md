# ADR-0006: Continuous Commercial Work Loop

- Status: Accepted
- Lifecycle: repository mirror `active_pr` #824; runtime `downstream`
- Date: 2026-08-09
- Supersedes: implicit completion when one assigned item or queue becomes empty

## Context

The conversation identified premature stopping as a delivery defect: completing
one change did not complete the documentation, review, CI, release, merge, or
next-priority loop. The executable schedule and prompt live in an external
ChatGPT automation, while repository decisions and evidence must remain
reviewable without exposing credentials or pretending that Git history proves
the automation ran.

## Decision

Use an hourly external commercial work loop, mirrored by
[`docs/automation-contract.md`](../automation-contract.md). Each cycle performs
exact-head review, documentation sufficiency evaluation, safe remediation,
verification, push/PR/check follow-through, guarded merge, and next-item
selection. An empty immediate queue starts backlog and coverage re-evaluation;
it is not a terminal success condition.

Runtime prompt/schedule state remains `downstream`. The repository stores the
non-secret behavioral contract and run-evidence schema. The loop does not
bypass permissions, destructive-action approval, branch protection, required
review, security gates, or blocked visual evidence.

## Alternatives considered

- Stop after the currently named task: rejected because it leaves related
  documentation, checks, review findings and release evidence unfinished.
- Stop when an issue queue is empty: rejected because coverage gaps, failed or
  queued checks, planned requirements and stale evidence can remain.
- Encode the whole loop only as GitHub Actions: rejected because the current
  cross-tool conversation/automation authority is external and GitHub Actions
  must not receive unnecessary interactive credentials.
- Keep the rule only in chat: rejected because it is not durable or reviewable
  with repository decisions.

## Consequences

- Every run must distinguish uncommitted, active-PR, protected-main, planned,
  downstream and externally blocked evidence.
- The loop may uncover additional safe work, but cannot invent authorization or
  expand into destructive/high-risk scope without approval.
- Repository and external runtime state can drift; the next run must detect and
  report that drift rather than silently choosing one.
- “No remaining work” requires an explicit re-evaluation record, not absence of
  queued tasks.

## Verification

- The external automation is enabled with the recorded identity, hourly
  cadence, timezone, documentation-sufficiency clause and `NO EMPTY-QUEUE STOP`
  semantics.
- The documentation contract checks that the repository mirror and this ADR
  remain in the canonical authority graph.
- Run reports bind changes and checks to exact SHAs and name the next item or a
  real authority/safety blocker.

## References

- [Automation contract](../automation-contract.md)
- [Documentation authority](../README.md)
- [Release plan](../release-plan.md)
