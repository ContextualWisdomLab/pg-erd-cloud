#!/usr/bin/env bash
set -euo pipefail

repo_root="$(
  CDPATH=''
  cd -P -- "$(dirname -- "$0")/../.."
  pwd -P
)"
workflow_file="$repo_root/.github/workflows/opencode-review.yml"

check_contains() {
  local needle="$1"
  if ! grep -Fq -- "$needle" "$workflow_file"; then
    printf 'missing OpenCode fact-gate contract: %s\n' "$needle" >&2
    exit 1
  fi
}

check_contains '## Changed docs repository tree evidence'
check_contains 'git ls-tree -r --name-only HEAD -- "$docs_dir"'
check_contains 'Do not claim repository docs, images, or reference assets are unavailable, missing, or absent unless the changed docs repository tree evidence proves it.'
check_contains 'collect_unresolved_human_review_threads()'
check_contains 'reviewThreads(first: 100)'
check_contains 'Latest unresolved human review thread evidence'
check_contains 'OpenCode reviewed the current-head evidence but found unresolved human review threads before approval.'

printf 'OpenCode fact-gate contract OK\n'
