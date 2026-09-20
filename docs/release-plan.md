# Release, Rollback, and Recovery Plan

Status date: 2026-08-09
Current PR #824: not release-ready at the last exact-head audit

## Release classes

| Class | Examples | Minimum additional evidence |
| --- | --- | --- |
| Documentation/design | ADR/PRD/TRD/Figma contract | Link/diagram/traceability tests and domain review; never implies runtime delivery |
| UI/API compatible | PR #824 share/UI hardening | Unit/component/API, browser/a11y/visual, security and backward-compatibility evidence |
| Dependency | `nanoid` lock remediation | Real advisory reproduction, fixed dependency tree/audit, owning package build/tests |
| Application schema | Alembic migration | Upgrade from supported versions, ORM/schema comparison, backup/restore and app rollback |
| Target write capability | Future FE-100..190 | Full safety case, staged rollout, recovery drill and independent DBA/security approval |

## Exact-head readiness checklist

1. Freeze the candidate SHA and base SHA; regenerate the traceability and
   documentation coverage rows for that head.
2. Review the complete diff for unrelated files, generated artifacts, secrets,
   migration compatibility, public contract and Figma authority.
3. Run backend mypy/pytest and frontend clean install/type/test/build; run the
   change-specific security, browser, database and recovery suites.
4. Require every branch-protection check to report success on the candidate.
   Queued, skipped, neutral, stale, provider-failed or base-only evidence does
   not count.
5. Resolve every review thread and obtain independent review. A bot that skips
   draft PRs is not a review.
6. Attach SBOM/provenance and deployment/migration/rollback evidence appropriate
   to the release class.
7. Mark ready and merge only without bypassing the ruleset.

## Deployment sequence

- Back up and restore-test application PostgreSQL when a migration is present.
- Deploy to an isolated staging environment from the exact immutable artifact.
- Run health, authenticated smoke, share boundary, migrations, observability and
  connector checks through production-like routing.
- Canary or limit tenants for risky changes; monitor the named SLO/error/queue
  signals and compare to predeploy baseline.
- Promote the same artifact. Record time, actor, SHA/image digest, migration
  revision and verification results.

## Rollback decision

| Change | Safe rollback direction |
| --- | --- |
| Additive UI/API | Redeploy prior immutable artifact after compatibility smoke |
| Additive DB schema | Prior app may run only if forward/backward compatibility was tested |
| Destructive/contract DB schema | Do not binary-rollback; restore/forward-fix through approved recovery plan |
| Dependency-only | Revert only if doing so does not reintroduce the validated vulnerability; otherwise forward-fix |
| Public representation | Remove/disable exposure at server boundary; browser-only hiding is insufficient |
| Partially committed target DDL | Never claim global rollback; enter explicit recoverable state and follow plan evidence |

## PR #824 current disposition

At audited head `385af924` on 2026-08-09 11:33 UTC, the GitHub frontend/backend,
Semgrep, CodeQL and central security jobs had succeeded, with no formal review
or review thread. Required Strix GitHub run `31306453112` (job `93227506608`)
completed `failure`: its primary provider returned HTTP 429, then fallback
reported vulnerable `nanoid@3.3.16` and failed closed when it could not map a
structured artifact to changed files. Documentation and dependency work after
that SHA invalidates the old rollup and requires a fresh exact-head run; the
same-viewport browser/Figma signoff is still blocked. The current working tree pins
`nanoid` to patched `3.3.17` and passes a local npm audit; this is remediation
evidence, not a replacement for the required commit-bound rerun.

## Post-release verification

Observe at least the release-specific risk window for health/error/latency,
authorization failures, public-share responses, queue age/stuck work, target
connector errors, unexpected egress, dependency alerts and user-reported
regressions. Close the release only when rollback/recovery evidence and residual
issues are linked to owners; then update CHANGELOG, docs lifecycle labels and
the protected-main traceability matrix.
