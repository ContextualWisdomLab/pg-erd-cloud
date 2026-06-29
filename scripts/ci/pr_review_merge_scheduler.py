#!/usr/bin/env python3
"""Schedule-safe PR review and merge queue worker.

The worker is intentionally conservative: it only merges a PR when current-head
approval exists, no current-head change-request review exists, review threads are
resolved, GitHub checks are not failed or pending, and GitHub reports the head as
mergeable. Missing evidence blocks the merge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any


OK_CHECK_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}
FAILED_CHECK_CONCLUSIONS = {
    "ACTION_REQUIRED",
    "CANCELLED",
    "FAILURE",
    "STARTUP_FAILURE",
    "TIMED_OUT",
}
OK_STATUS_STATES = {"SUCCESS"}
PENDING_STATUS_STATES = {"EXPECTED", "PENDING"}
MERGEABLE_STATES = {"CLEAN", "HAS_HOOKS", "UNSTABLE"}
OPEN_CODE_REVIEW_MARKER = "OpenCode Agent"
DISPATCH_MARKER = "<!-- pr-review-merge-scheduler opencode-dispatch"


class GhError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckSummary:
    failed: tuple[str, ...]
    pending: tuple[str, ...]


@dataclass(frozen=True)
class ReviewSummary:
    approved: bool
    change_requested: bool
    approval_sources: tuple[str, ...]
    change_sources: tuple[str, ...]
    has_current_opencode_review: bool


@dataclass(frozen=True)
class PullRequestDecision:
    number: int
    action: str
    reasons: tuple[str, ...]


def run_gh_json(args: list[str]) -> Any:
    command = ["gh", *args]
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise GhError(
            f"{' '.join(command)} failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    try:
        return json.loads(completed.stdout or "null")
    except json.JSONDecodeError as exc:
        raise GhError(f"{' '.join(command)} returned invalid JSON: {exc}") from exc


def run_gh(args: list[str], *, dry_run: bool) -> None:
    command = ["gh", *args]
    if dry_run:
        print("DRY-RUN:", " ".join(command))
        return
    completed = subprocess.run(command, check=False, text=True)
    if completed.returncode != 0:
        raise GhError(f"{' '.join(command)} failed with exit {completed.returncode}")


def actor_login(review: dict[str, Any]) -> str:
    user = review.get("user") or {}
    return str(user.get("login") or review.get("author", {}).get("login") or "")


def review_mentions_head(body: str, head_sha: str) -> bool:
    return (
        head_sha in body
        or f"Head SHA: `{head_sha}`" in body
        or f"head_sha={head_sha}" in body
    )


def review_is_current(review: dict[str, Any], head_sha: str) -> bool:
    commit_id = str(review.get("commit_id") or "")
    body = str(review.get("body") or "")
    return commit_id == head_sha or review_mentions_head(body, head_sha)


def summarize_reviews(reviews: list[dict[str, Any]], head_sha: str) -> ReviewSummary:
    approvals: list[str] = []
    changes: list[str] = []
    has_current_opencode_review = False

    for review in reviews:
        state = str(review.get("state") or "").upper()
        if state not in {"APPROVED", "CHANGES_REQUESTED"}:
            continue
        if not review_is_current(review, head_sha):
            continue

        login = actor_login(review) or "unknown"
        body = str(review.get("body") or "")
        if OPEN_CODE_REVIEW_MARKER in body or "opencode" in login.lower():
            has_current_opencode_review = True

        source = f"{login}:{state}"
        if state == "APPROVED":
            approvals.append(source)
        elif state == "CHANGES_REQUESTED":
            changes.append(source)

    return ReviewSummary(
        approved=bool(approvals),
        change_requested=bool(changes),
        approval_sources=tuple(approvals),
        change_sources=tuple(changes),
        has_current_opencode_review=has_current_opencode_review,
    )


def check_name(node: dict[str, Any]) -> str:
    if node.get("__typename") == "CheckRun":
        workflow = (
            (node.get("checkSuite") or {})
            .get("workflowRun", {})
            .get("workflow", {})
            .get("name")
        )
        name = str(node.get("name") or "check")
        return f"{workflow}/{name}" if workflow else name
    return str(node.get("context") or "status")


def summarize_checks(status_rollup: list[dict[str, Any]] | None) -> CheckSummary:
    failed: list[str] = []
    pending: list[str] = []
    for node in status_rollup or []:
        typename = node.get("__typename")
        name = check_name(node)
        if typename == "CheckRun":
            status = str(node.get("status") or "").upper()
            conclusion = str(node.get("conclusion") or "").upper()
            if status != "COMPLETED":
                pending.append(f"{name}:{status or 'UNKNOWN'}")
            elif conclusion in FAILED_CHECK_CONCLUSIONS:
                failed.append(f"{name}:{conclusion}")
            elif conclusion not in OK_CHECK_CONCLUSIONS:
                pending.append(f"{name}:{conclusion or 'UNKNOWN'}")
        elif typename == "StatusContext":
            state = str(node.get("state") or "").upper()
            if state in OK_STATUS_STATES:
                continue
            if state in PENDING_STATUS_STATES:
                pending.append(f"{name}:{state}")
            else:
                failed.append(f"{name}:{state or 'UNKNOWN'}")
    return CheckSummary(failed=tuple(failed), pending=tuple(pending))


def repo_parts(repo: str) -> tuple[str, str]:
    owner, separator, name = repo.partition("/")
    if not owner or not separator or not name:
        raise ValueError(f"repo must be OWNER/NAME, got {repo!r}")
    return owner, name


def unresolved_review_threads(repo: str, number: int) -> int:
    owner, name = repo_parts(repo)
    after: str | None = None
    unresolved = 0

    while True:
        query = """
        query($owner:String!, $name:String!, $number:Int!, $after:String) {
          repository(owner:$owner, name:$name) {
            pullRequest(number:$number) {
              reviewThreads(first: 100, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes { isResolved isOutdated }
              }
            }
          }
        }
        """
        gh_args = [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={number}",
        ]
        if after is not None:
            gh_args.extend(["-f", f"after={after}"])
        result = run_gh_json(gh_args)
        if result is None:
            raise GhError("reviewThreads query returned no data")

        pr = result.get("data", {}).get("repository", {}).get("pullRequest")
        if not pr:
            raise GhError(f"could not read review threads for PR #{number}")
        threads = pr.get("reviewThreads") or {}
        for thread in threads.get("nodes") or []:
            if not thread.get("isResolved") and not thread.get("isOutdated"):
                unresolved += 1
        page_info = threads.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            return unresolved
        after = page_info.get("endCursor")


def list_prs(repo: str, limit: int) -> list[dict[str, Any]]:
    return run_gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number,title,headRefName,baseRefName,headRefOid,baseRefOid,isDraft,updatedAt",
        ]
    )


def pr_view(repo: str, number: int) -> dict[str, Any]:
    return run_gh_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            ",".join(
                [
                    "number",
                    "title",
                    "headRefName",
                    "baseRefName",
                    "headRefOid",
                    "baseRefOid",
                    "mergeable",
                    "mergeStateStatus",
                    "reviewDecision",
                    "statusCheckRollup",
                    "autoMergeRequest",
                    "isDraft",
                    "url",
                ]
            ),
        ]
    )


def pr_reviews(repo: str, number: int) -> list[dict[str, Any]]:
    pages = run_gh_json(
        ["api", f"repos/{repo}/pulls/{number}/reviews", "--paginate", "--slurp"]
    )
    return [review for page in pages for review in page]


def issue_comments(repo: str, number: int) -> list[dict[str, Any]]:
    pages = run_gh_json(
        ["api", f"repos/{repo}/issues/{number}/comments", "--paginate", "--slurp"]
    )
    return [comment for page in pages for comment in page]


def should_skip_dispatch_for_recent_marker(
    comments: list[dict[str, Any]],
    head_sha: str,
    min_interval_seconds: int,
) -> bool:
    now = int(time.time())
    marker_re = re.compile(
        r"<!-- pr-review-merge-scheduler opencode-dispatch "
        r"head_sha=([0-9a-fA-F]{40}) epoch=([0-9]+) -->"
    )
    for comment in reversed(comments):
        body = str(comment.get("body") or "")
        match = marker_re.search(body)
        if not match:
            continue
        if match.group(1).lower() != head_sha.lower():
            continue
        try:
            epoch = int(match.group(2))
        except ValueError:
            continue
        return now - epoch < min_interval_seconds
    return False


def create_dispatch_marker(
    repo: str, number: int, head_sha: str, *, dry_run: bool
) -> None:
    body = "\n".join(
        [
            f"{DISPATCH_MARKER} head_sha={head_sha} epoch={int(time.time())} -->",
            "",
            "Scheduled OpenCode review dispatch for this PR head.",
            "",
            f"- Head SHA: `{head_sha}`",
        ]
    )
    if dry_run:
        print(f"DRY-RUN: would create dispatch marker on PR #{number}")
        return
    run_gh(
        [
            "api",
            "-X",
            "POST",
            f"repos/{repo}/issues/{number}/comments",
            "-f",
            f"body={body}",
        ],
        dry_run=False,
    )


def dispatch_opencode_review(repo: str, pr: dict[str, Any], *, dry_run: bool) -> None:
    args = [
        "workflow",
        "run",
        "opencode-review.yml",
        "--repo",
        repo,
        "-f",
        f"pr_number={pr['number']}",
        "-f",
        f"pr_base_ref={pr['baseRefName']}",
        "-f",
        f"pr_base_sha={pr['baseRefOid']}",
        "-f",
        f"pr_head_sha={pr['headRefOid']}",
    ]
    run_gh(args, dry_run=dry_run)


def merge_pr(
    repo: str, number: int, head_sha: str, method: str, *, auto: bool, dry_run: bool
) -> None:
    args = [
        "pr",
        "merge",
        str(number),
        "--repo",
        repo,
        f"--{method}",
        "--match-head-commit",
        head_sha,
    ]
    if auto:
        args.append("--auto")
    run_gh(args, dry_run=dry_run)


def decide(
    pr: dict[str, Any],
    reviews: ReviewSummary,
    checks: CheckSummary,
    unresolved_threads: int,
) -> PullRequestDecision:
    number = int(pr["number"])
    reasons: list[str] = []

    if pr.get("isDraft"):
        return PullRequestDecision(number, "skip", ("draft PR",))
    if unresolved_threads > 0:
        reasons.append(f"{unresolved_threads} unresolved review thread(s)")
    if reviews.change_requested:
        reasons.append(
            "current-head change request: " + ", ".join(reviews.change_sources)
        )
    if not reviews.approved:
        reasons.append("no current-head approval")
    if checks.failed:
        reasons.append("failed checks: " + ", ".join(checks.failed))

    mergeable = str(pr.get("mergeable") or "")
    merge_state = str(pr.get("mergeStateStatus") or "")
    if mergeable != "MERGEABLE":
        reasons.append(f"mergeable={mergeable or 'UNKNOWN'}")
    if merge_state == "DIRTY":
        reasons.append("merge conflict")
    elif merge_state and merge_state not in MERGEABLE_STATES:
        reasons.append(f"mergeStateStatus={merge_state}")

    if reasons:
        return PullRequestDecision(number, "block", tuple(reasons))
    if checks.pending:
        return PullRequestDecision(
            number,
            "auto-merge",
            ("pending checks: " + ", ".join(checks.pending),),
        )
    return PullRequestDecision(
        number, "merge", ("current-head approval and clean checks",)
    )


def process_queue(args: argparse.Namespace) -> int:
    prs = list_prs(args.repo, args.max_prs)
    print(f"Found {len(prs)} open PR(s) in {args.repo}.")
    merged = 0
    auto_merged = 0
    dispatched = 0
    blocked = 0

    for item in prs:
        number = int(item["number"])
        pr = pr_view(args.repo, number)
        head_sha = str(pr["headRefOid"])
        print(f"::group::PR #{number} {pr.get('title', '')}")
        try:
            reviews = summarize_reviews(pr_reviews(args.repo, number), head_sha)
            checks = summarize_checks(pr.get("statusCheckRollup"))
            unresolved = unresolved_review_threads(args.repo, number)
            decision = decide(pr, reviews, checks, unresolved)
            print(
                json.dumps(
                    {
                        "number": number,
                        "head": head_sha,
                        "decision": decision.action,
                        "reasons": decision.reasons,
                        "approvals": reviews.approval_sources,
                        "changes": reviews.change_sources,
                    },
                    ensure_ascii=False,
                )
            )

            if decision.action == "merge":
                merge_pr(
                    args.repo,
                    number,
                    head_sha,
                    args.merge_method,
                    auto=False,
                    dry_run=args.dry_run,
                )
                merged += 1
            elif decision.action == "auto-merge":
                merge_pr(
                    args.repo,
                    number,
                    head_sha,
                    args.merge_method,
                    auto=True,
                    dry_run=args.dry_run,
                )
                auto_merged += 1
            else:
                blocked += 1
                if (
                    args.trigger_reviews
                    and not reviews.has_current_opencode_review
                    and not pr.get("isDraft")
                    and not reviews.change_requested
                ):
                    comments = issue_comments(args.repo, number)
                    if should_skip_dispatch_for_recent_marker(
                        comments,
                        head_sha,
                        args.review_retry_hours * 3600,
                    ):
                        print(
                            "OpenCode review dispatch skipped: recent marker exists for this head."
                        )
                    else:
                        dispatch_opencode_review(args.repo, pr, dry_run=args.dry_run)
                        create_dispatch_marker(
                            args.repo, number, head_sha, dry_run=args.dry_run
                        )
                        dispatched += 1
        except GhError as exc:
            blocked += 1
            print(f"BLOCKED: PR #{number}: {exc}", file=sys.stderr)
        finally:
            print("::endgroup::")

    print(
        json.dumps(
            {
                "merged": merged,
                "auto_merge_enabled": auto_merged,
                "review_dispatches": dispatched,
                "blocked_or_skipped": blocked,
            },
            ensure_ascii=False,
        )
    )
    return 0


def self_test() -> int:
    head = "a" * 40
    reviews = [
        {
            "state": "APPROVED",
            "commit_id": head,
            "user": {"login": "opencode-agent[bot]"},
            "body": "",
        },
        {
            "state": "CHANGES_REQUESTED",
            "commit_id": "b" * 40,
            "user": {"login": "coderabbitai[bot]"},
            "body": "",
        },
    ]
    summary = summarize_reviews(reviews, head)
    assert summary.approved
    assert not summary.change_requested
    assert summary.has_current_opencode_review

    checks = summarize_checks(
        [
            {
                "__typename": "CheckRun",
                "name": "backend",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
            {
                "__typename": "StatusContext",
                "context": "CodeRabbit",
                "state": "SUCCESS",
            },
        ]
    )
    assert checks.failed == ()
    assert checks.pending == ()

    decision = decide(
        {
            "number": 1,
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
        },
        summary,
        checks,
        0,
    )
    assert decision.action == "merge"

    blocked = decide(
        {
            "number": 2,
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
        },
        ReviewSummary(
            approved=True,
            change_requested=True,
            approval_sources=("opencode-agent[bot]:APPROVED",),
            change_sources=("coderabbitai[bot]:CHANGES_REQUESTED",),
            has_current_opencode_review=True,
        ),
        checks,
        0,
    )
    assert blocked.action == "block"
    assert "current-head change request" in blocked.reasons[0]

    pending = summarize_checks(
        [{"__typename": "CheckRun", "name": "frontend", "status": "IN_PROGRESS"}]
    )
    auto = decide(
        {
            "number": 3,
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
        },
        summary,
        pending,
        0,
    )
    assert auto.action == "auto-merge"

    comments = [
        {
            "body": (
                "<!-- pr-review-merge-scheduler opencode-dispatch "
                f"head_sha={head} epoch={int(time.time())} -->"
            )
        }
    ]
    assert should_skip_dispatch_for_recent_marker(comments, head, 24 * 3600)
    print("self-test passed")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--max-prs", type=int, default=50)
    parser.add_argument(
        "--merge-method", choices=("merge", "squash", "rebase"), default="merge"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--trigger-reviews", action="store_true")
    parser.add_argument("--review-retry-hours", type=int, default=24)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return args
    if not args.repo:
        parser.error("--repo is required outside GitHub Actions")
    if args.max_prs < 1:
        parser.error("--max-prs must be positive")
    if args.review_retry_hours < 1:
        parser.error("--review-retry-hours must be positive")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    return process_queue(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
