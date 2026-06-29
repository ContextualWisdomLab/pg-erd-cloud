import json
import subprocess
from typing import Any

class GhError(RuntimeError):
    pass

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
