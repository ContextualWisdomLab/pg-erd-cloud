#!/usr/bin/env python3
"""Dispatch conservative PR autofix runs for actionable review feedback."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Any

from pr_review_merge_scheduler import (
    GhError,
    issue_comments,
    pr_reviews,
    pr_view,
    run_gh,
    run_gh_json,
    summarize_reviews,
    unresolved_review_threads,
)


FIX_MARKER = "<!-- pr-review-fix-scheduler autofix-dispatch"


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


def pull_head_repo(repo: str, number: int) -> tuple[str, str]:
    pull = run_gh_json(["api", f"repos/{repo}/pulls/{number}"])
    head = pull.get("head") or {}
    head_repo = head.get("repo") or {}
    return str(head_repo.get("full_name") or ""), str(head.get("ref") or "")


def recent_fix_marker_exists(
    comments: list[dict[str, Any]],
    head_sha: str,
    min_interval_seconds: int,
) -> bool:
    now = int(time.time())
    marker_re = re.compile(
        r"<!-- pr-review-fix-scheduler autofix-dispatch "
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


def create_fix_marker(repo: str, pr: dict[str, Any], *, dry_run: bool) -> None:
    number = int(pr["number"])
    head_sha = str(pr["headRefOid"])
    body = "\n".join(
        [
            f"{FIX_MARKER} head_sha={head_sha} epoch={int(time.time())} -->",
            "",
            "Scheduled review-feedback autofix for this PR head.",
            "",
            f"- Head SHA: `{head_sha}`",
        ]
    )
    if dry_run:
        print(f"DRY-RUN: would create autofix marker on PR #{number}")
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


def dispatch_autofix(repo: str, pr: dict[str, Any], *, dry_run: bool) -> None:
    args = [
        "workflow",
        "run",
        "pr-review-autofix.yml",
        "--repo",
        repo,
        "-f",
        f"pr_number={pr['number']}",
        "-f",
        f"pr_base_ref={pr['baseRefName']}",
        "-f",
        f"pr_base_sha={pr['baseRefOid']}",
        "-f",
        f"pr_head_ref={pr['headRefName']}",
        "-f",
        f"pr_head_sha={pr['headRefOid']}",
    ]
    run_gh(args, dry_run=dry_run)


def needs_autofix(repo: str, pr: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    number = int(pr["number"])
    head_sha = str(pr["headRefOid"])
    reasons: list[str] = []

    review_summary = summarize_reviews(pr_reviews(repo, number), head_sha)
    unresolved_threads = unresolved_review_threads(repo, number)
    if review_summary.change_requested:
        reasons.append("current-head change request: " + ", ".join(review_summary.change_sources))
    if unresolved_threads:
        reasons.append(f"{unresolved_threads} unresolved review thread(s)")
    return bool(reasons), tuple(reasons)


def process_queue(args: argparse.Namespace) -> int:
    dispatched = 0
    inspected = 0
    prs = list_prs(args.repo, args.max_prs)
    print(f"Found {len(prs)} open PR(s) in {args.repo}.")

    for item in prs:
        if dispatched >= args.max_dispatches:
            break
        inspected += 1
        number = int(item["number"])
        pr = pr_view(args.repo, number)
        head_sha = str(pr["headRefOid"])
        print(f"::group::PR #{number} {pr.get('title', '')}")
        try:
            if pr.get("isDraft"):
                print("skip: draft PR")
                continue
            head_repo, head_ref = pull_head_repo(args.repo, number)
            if head_repo != args.repo:
                print(f"skip: fork PR head repo {head_repo}")
                continue
            if not head_ref or head_ref != pr.get("headRefName"):
                print(f"skip: head ref mismatch {head_ref!r}")
                continue

            needs_fix, reasons = needs_autofix(args.repo, pr)
            print(json.dumps({"number": number, "head": head_sha, "needs_fix": needs_fix, "reasons": reasons}))
            if not needs_fix:
                continue

            comments = issue_comments(args.repo, number)
            if recent_fix_marker_exists(comments, head_sha, args.retry_hours * 3600):
                print("skip: recent autofix marker exists for this head")
                continue

            dispatch_autofix(args.repo, pr, dry_run=args.dry_run)
            create_fix_marker(args.repo, pr, dry_run=args.dry_run)
            dispatched += 1
        except GhError as exc:
            print(f"BLOCKED: PR #{number}: {exc}", file=sys.stderr)
        finally:
            print("::endgroup::")

    print(json.dumps({"inspected": inspected, "autofix_dispatches": dispatched}))
    return 0


def self_test() -> int:
    head = "a" * 40
    comments = [
        {
            "body": (
                "<!-- pr-review-fix-scheduler autofix-dispatch "
                f"head_sha={head} epoch={int(time.time())} -->"
            )
        }
    ]
    assert recent_fix_marker_exists(comments, head, 24 * 3600)
    assert not recent_fix_marker_exists(comments, "b" * 40, 24 * 3600)
    print("self-test passed")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--max-prs", type=int, default=50)
    parser.add_argument("--max-dispatches", type=int, default=1)
    parser.add_argument("--retry-hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return args
    if not args.repo:
        parser.error("--repo is required outside GitHub Actions")
    if args.max_prs < 1:
        parser.error("--max-prs must be positive")
    if args.max_dispatches < 1:
        parser.error("--max-dispatches must be positive")
    if args.retry_hours < 1:
        parser.error("--retry-hours must be positive")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    return process_queue(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
