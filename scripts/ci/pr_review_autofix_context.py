#!/usr/bin/env python3
"""Collect bounded PR review feedback for the autofix worker."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_json(args: list[str]) -> Any:
    completed = subprocess.run(
        ["gh", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())
    return json.loads(completed.stdout or "null")


def repo_parts(repo: str) -> tuple[str, str]:
    owner, separator, name = repo.partition("/")
    if not owner or not separator or not name:
        raise ValueError(f"repo must be OWNER/NAME, got {repo!r}")
    return owner, name


def pr_view(repo: str, number: int) -> dict[str, Any]:
    return run_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,headRefName,baseRefName,headRefOid,baseRefOid,mergeStateStatus,statusCheckRollup,url",
        ]
    )


def current_reviews(repo: str, number: int, head_sha: str) -> list[dict[str, Any]]:
    pages = run_json(["api", f"repos/{repo}/pulls/{number}/reviews", "--paginate", "--slurp"])
    reviews = [review for page in pages for review in page]
    current: list[dict[str, Any]] = []
    for review in reviews:
        body = str(review.get("body") or "")
        commit_id = str(review.get("commit_id") or "")
        if commit_id != head_sha and head_sha not in body:
            continue
        if str(review.get("state") or "").upper() not in {"CHANGES_REQUESTED", "APPROVED"}:
            continue
        current.append(review)
    return current[-8:]


def review_threads(repo: str, number: int) -> list[dict[str, Any]]:
    owner, name = repo_parts(repo)
    query = """
    query($owner:String!, $name:String!, $number:Int!) {
      repository(owner:$owner, name:$name) {
        pullRequest(number:$number) {
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              isOutdated
              comments(first: 20) {
                nodes {
                  author { login }
                  body
                  path
                  line
                  originalLine
                  diffHunk
                  createdAt
                }
              }
            }
          }
        }
      }
    }
    """
    result = run_json(
        [
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
    )
    nodes = result["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    return [
        node
        for node in nodes
        if not node.get("isResolved") and not node.get("isOutdated")
    ]


def check_summary(status_rollup: list[dict[str, Any]] | None) -> list[str]:
    lines: list[str] = []
    for node in status_rollup or []:
        if node.get("__typename") == "CheckRun":
            name = str(node.get("name") or "check")
            workflow = str(node.get("workflowName") or "")
            label = f"{workflow}/{name}" if workflow else name
            status = str(node.get("status") or "")
            conclusion = str(node.get("conclusion") or "")
            lines.append(f"- {label}: {status} {conclusion}".rstrip())
        elif node.get("__typename") == "StatusContext":
            lines.append(f"- {node.get('context')}: {node.get('state')}")
    return lines


def write_context(repo: str, number: int, head_sha: str, output: Path) -> None:
    pr = pr_view(repo, number)
    if pr["headRefOid"] != head_sha:
        raise RuntimeError(f"live head {pr['headRefOid']} does not match expected {head_sha}")

    reviews = current_reviews(repo, number, head_sha)
    threads = review_threads(repo, number)

    lines = [
        "# PR Review Autofix Context",
        "",
        f"- Repo: {repo}",
        f"- PR: #{number}",
        f"- URL: {pr.get('url')}",
        f"- Title: {pr.get('title')}",
        f"- Base: {pr.get('baseRefName')} @ {pr.get('baseRefOid')}",
        f"- Head: {pr.get('headRefName')} @ {head_sha}",
        f"- Merge state: {pr.get('mergeStateStatus')}",
        "",
        "## Current Reviews",
        "",
    ]

    if reviews:
        for review in reviews:
            login = (review.get("user") or {}).get("login", "unknown")
            body = str(review.get("body") or "").strip()
            lines.extend(
                [
                    f"### {review.get('state')} by {login}",
                    "",
                    body[:6000] if body else "(empty body)",
                    "",
                ]
            )
    else:
        lines.append("(no current-head review objects)")
        lines.append("")

    lines.extend(["## Unresolved Review Threads", ""])
    if threads:
        for thread in threads:
            lines.append(f"### Thread {thread.get('id')}")
            lines.append("")
            for comment in (thread.get("comments") or {}).get("nodes") or []:
                login = (comment.get("author") or {}).get("login", "unknown")
                path = comment.get("path") or "(no path)"
                line = comment.get("line") or comment.get("originalLine") or ""
                body = str(comment.get("body") or "").strip()
                lines.extend(
                    [
                        f"- {login} at {path}:{line}",
                        "",
                        body[:6000] if body else "(empty body)",
                        "",
                    ]
                )
    else:
        lines.append("(no unresolved non-outdated review threads)")
        lines.append("")

    lines.extend(["## Status Checks", ""])
    lines.extend(check_summary(pr.get("statusCheckRollup")))
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("--repo is required")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    write_context(args.repo, args.pr_number, args.head_sha, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
