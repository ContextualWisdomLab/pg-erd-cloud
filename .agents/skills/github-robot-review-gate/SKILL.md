---
name: github-robot-review-gate
description: >-
  Use when GitHub PR merge gates, CodeRabbit robot-review policy, required
  review settings, stale status contexts, or temporary required-check rollbacks
  are blocking or being misdiagnosed.
---

# GitHub Robot Review Gate

## Core rule

Diagnose the exact merge blocker before changing code or repository settings.
CodeRabbit/check-run success can satisfy this repo's robot-review policy only
when current-head CodeRabbit blocking findings, warnings, and failures are fixed,
rebutted with evidence, or superseded. It is not a GitHub `APPROVED` review. If
GitHub rulesets require human approval, fix the ruleset contract rather than
waiting for humans or disabling security.

## Root-cause-first workflow

1. Capture the PR head SHA, mergeability, review decision, required checks, and
   rule evaluation before proposing a fix.
2. Separate four signals: GitHub review state, CodeRabbit robot-review evidence,
   required status contexts, and ruleset settings.
3. Identify the narrow blocker: missing current-head robot evidence, unresolved
   robot findings, human-review ruleset count, unresolved threads, stale status
   context, or failing check.
4. Apply only the minimal reversible fix, then re-capture the same evidence.

## Evidence commands

```bash
gh pr view <pr> \
  --json number,headRefOid,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,latestReviews
gh pr checks <pr> --required
gh api repos/<owner>/<repo>/pulls/<pr>/reviews
gh api repos/<owner>/<repo>/commits/<sha>/status
gh api repos/<owner>/<repo>/commits/<sha>/check-runs
gh api repos/<owner>/<repo>/rulesets \
  --jq '.[] | {name, enforcement, conditions, rules}'
```

Record the current head SHA with every screenshot, review, and check summary so
stale evidence is not mistaken for current-head approval.

## Guardrails

- Do not bypass branch protection, add bypass actors, use admin merge, force
  push, dismiss reviews, or disable security checks unless explicitly requested.
- Do not treat `Review skipped`, CodeRabbit walkthroughs, or check-run success as
  a GitHub `APPROVED` review object. They are robot-review gate evidence only.
- Do not wait for human review by default in this repo when robot-review policy
  applies; instead verify `required_approving_review_count=0`.
- Do not remove required review thread resolution; keep
  `required_review_thread_resolution=true`.

## Stale required status contexts

If a PR that hardens or restores a workflow is blocked by a stale required
context (for example `strix` while fixing Strix), document the stale context and
use a temporary, reversible ruleset adjustment only when necessary. Capture
equivalent temporary evidence before merge, such as a trusted-base rerun,
scanner artifact, SARIF output, or manual security review evidence tied to the
current head SHA. The rollback requirement is part of the fix: restore the
`strix` required context immediately after the hardened workflow emits that
context successfully on the protected branch.

## Safe temporary handling

- Prefer rerunning or updating the branch before touching rulesets.
- If temporary removal is unavoidable, capture before/after ruleset JSON, owner,
  expiry, current head SHA, equivalent temporary evidence, and a dated rollback
  note in the PR.
- Restore required contexts and confirm `gh pr checks --required` shows the
  hardened context before declaring the gate resolved.

## Common mistakes

- Equating CodeRabbit status with GitHub `APPROVED`: treat it as repo
  robot-review evidence, then check ruleset review count.
- Waiting for human review despite policy: verify ruleset count is zero and
  robot evidence is current-head.
- Removing `strix` permanently to unblock Strix fixes: temporarily remove only
  with evidence, then restore once Strix emits.
- Disabling scanners to merge faster: keep security gates on; fix the gate
  contract or the failing scanner.
