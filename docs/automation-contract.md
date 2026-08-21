# Commercial Work-Loop Automation Contract

Status date: 2026-08-09
Repository contract lifecycle: `active_pr` #824
Runtime lifecycle: `downstream` ChatGPT automation
Runtime authority: `pg-erd-cloud Commercial Loop`
(`6a700cace240819197eaae6e80169e49`), hourly, `Asia/Seoul`

This document captures the non-secret operating contract requested in the
conversation. It does not pretend that a repository file creates, schedules,
or proves execution of the external automation.

## Objective

Continuously advance pg-erd-cloud toward a reviewable commercial release. A
cycle does not stop merely because the immediately assigned item is finished or
the current queue appears empty; it closes the current evidence loop and moves
to the next safe, highest-priority unresolved item.

## Required cycle

1. Read the exact protected-main and active-PR heads, unresolved review
   threads, required checks, security findings, visual evidence, documentation
   gaps, and previously recorded residual work.
2. Re-evaluate documentation sufficiency across ADR, PRD, TRD, Architecture,
   UML, ERD, API, threat, test, operations, release, traceability, Figma, and
   this automation contract. Use lifecycle labels; never infer delivery from a
   plan, chat, design, or documentation-only change.
3. Select the highest-priority safe item that is actionable with current
   authority. Fix root cause and its code, tests, contracts, and documentation
   together. Never weaken a security/review gate to obtain green status.
4. Run change-specific and full relevant verification. Bind evidence to the
   exact candidate tree; stale, queued, skipped, provider-failed, or base-only
   checks do not count as success.
5. Commit and push a coherent candidate, update the pull request, and monitor
   the new exact head. Resolve actionable review/CI findings and repeat.
6. Merge only when required checks, independent review, branch protection,
   documentation truth, release evidence, and required visual/browser signoff
   are satisfied.
7. After merge—or when one item is externally blocked—continue with the next
   safe item from documented P0/P1 gaps. **NO EMPTY-QUEUE STOP:** an empty
   immediate queue triggers backlog/coverage re-evaluation, not silent
   termination.

The loop pauses only for a user-requested pause, missing authority or
permission, an irreversible/destructive decision requiring approval, a safety
boundary, or an external dependency that leaves no other authorized work. A
blocker is reported precisely; the loop pivots to other safe work when one
exists.

## Evidence contract

Every run records, without secrets:

- timestamp, automation identity, repository, base SHA, candidate/head SHA and
  pull request;
- selected requirement/finding and lifecycle;
- files and contracts changed;
- exact verification commands/results and required GitHub check/review state;
- unresolved external blockers and the next selected item.

A local working tree is `uncommitted candidate work`, not `active_pr`. A pushed
head without its fresh required checks is not release-ready. A repository test
cannot prove that the external automation ran.

## Runtime and safety boundary

- The external automation configuration is authoritative for its enabled state,
  schedule, timezone, and executable prompt. This document is its reviewable
  mirror; runtime changes update this file in the next repository cycle.
- Credentials, connector secrets, internal system prompts, and access tokens
  are deliberately excluded. Existing task-relevant credentials may be used
  only through configured tools and policy boundaries.
- The automation cannot bypass GitHub protection, reviewer approval, Figma or
  browser evidence requirements, deployment ownership, or destructive-action
  confirmation.
- When runtime automation state cannot be queried, the run reports that limit
  instead of claiming schedule/prompt conformance.

## Review triggers

Update this contract when cadence, timezone, repository/PR scope, required
gates, lifecycle vocabulary, continuation semantics, merge policy, authority,
or stop conditions change. A material policy reversal requires a superseding
ADR.
