# CodeQL SAST backfill workflow

The `codeql-sast-backfill` workflow is a manual recovery path for improving
OpenSSF Scorecard SAST coverage after CodeQL upload was unavailable for part of
the recent `main` history.

## Intent

Scorecard evaluates whether recent commits have SAST results. The normal CodeQL
workflow now uploads CodeQL results for new pull requests, but older recent
commits still need analyses before the SAST coverage ratio catches up. This
workflow lets maintainers explicitly analyze recent commits on a target branch.

## Manual dispatch

Use the GitHub Actions UI and run `codeql-sast-backfill` with:

- `branch`: `main`
- `commit_count`: `30`

The workflow enumerates recent commits from `origin/<branch>` and analyzes each
commit for:

- `javascript-typescript`
- `python`

## Security contract

- The workflow is `workflow_dispatch` only, so it does not run on untrusted pull
  request code automatically.
- Repository contents are read-only except the analyze job, which requires
  `security-events: write` to upload CodeQL results.
- Checkout credentials are not persisted.
- The uploaded SARIF analysis is attributed to `refs/heads/<branch>` and the
  specific commit SHA selected by the matrix.
- `commit_count` is capped at `128` so the two-language matrix stays within the
  GitHub Actions 256-job limit.

## Verification

Run the static verifier before changing the workflow:

```powershell
python scripts\ci\validate_codeql_backfill.py
```

The verifier checks that the workflow remains manually dispatched, keeps the
expected inputs, grants `security-events: write` only where the CodeQL upload
needs it, and keeps the expected language matrix for this repository.
