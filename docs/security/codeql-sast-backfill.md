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

The workflow fetches the requested `refs/heads/<branch>` into an explicit
`refs/remotes/origin/<branch>` tracking ref, enumerates that ref, and analyzes
each commit for:

- `javascript-typescript`
- `python`

## Security contract

- The workflow is `workflow_dispatch` only, so it does not run on untrusted pull
  request code automatically.
- Repository contents are read-only except the analyze job, which requires
  `security-events: write` to upload CodeQL results.
- Checkout credentials are not persisted.
- Dispatch inputs enter shell steps only through reviewed `env` mappings.
  Branch input must be a valid branch name and must equal Git's normalized
  result, so previous-checkout aliases such as `@{-1}` are rejected before an
  explicit, option-terminated refspec is constructed.
- The uploaded SARIF analysis is attributed to `refs/heads/<branch>` and the
  specific commit SHA selected by the matrix.
- `commit_count` is capped at `127` so the two-language matrix plus the
  enumerate job stays within the GitHub Actions 256-job limit.

## Verification

Run the static verifier before changing the workflow:

```powershell
python scripts\ci\validate_codeql_backfill.py
```

The verifier checks that the workflow remains manually dispatched, keeps the
expected inputs, requires read-only workflow and enumeration permissions, and
grants `security-events: write` only to the CodeQL analysis job. It also keeps
the expected language matrix and exact-allowlists every workflow expression by
expression body and line location. Unknown contexts, direct or indexed input
access, function-wrapped input access, and relocated expressions are rejected.
Multiline or otherwise unparseable expressions fail closed. The verifier also
requires the normalized-branch equality guard.
