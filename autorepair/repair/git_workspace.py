from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from autorepair.audit_store import append_audit_event


PROTECTED_BRANCHES = {"main", "master", "develop"}


@dataclass
class WorktreeInfo:
    repo_path: str
    worktree_path: str
    repair_branch: str
    base_branch: str


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "repair"


def build_repair_branch(incident_id: str, title: str) -> str:
    incident_short = incident_id.replace("_", "-").lower()
    if incident_short.startswith("inc-"):
        incident_short = incident_short[4:]
    return f"autorepair/inc-{incident_short}-{_slugify(title)}"


def validate_repair_branch(branch: str) -> None:
    if branch in PROTECTED_BRANCHES:
        raise ValueError(f"Refusing to use protected branch as repair branch: {branch}")
    if not branch.startswith("autorepair/"):
        raise ValueError(f"Repair branch must start with autorepair/: {branch}")


def assert_safe_cleanup_branch(branch: str) -> None:
    validate_repair_branch(branch)


def _run_git(repo_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        text=True,
        capture_output=True,
        check=False,
    )
    append_audit_event(
        "git_command",
        None,
        {"repo_path": str(repo_path), "args": args, "returncode": result.returncode},
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def _branch_exists(repo_path: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        cwd=str(repo_path),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def create_repair_worktree(
    repo_path: str | Path,
    base_branch: str,
    repair_branch: str,
    incident_id: str,
) -> WorktreeInfo:
    validate_repair_branch(repair_branch)
    if base_branch in {"", repair_branch}:
        raise ValueError("Base branch must be different from repair branch")

    repo = Path(repo_path).resolve()
    worktree_path = repo / ".worktrees" / incident_id
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if worktree_path.exists():
        return WorktreeInfo(
            repo_path=str(repo),
            worktree_path=str(worktree_path),
            repair_branch=repair_branch,
            base_branch=base_branch,
        )

    if _branch_exists(repo, repair_branch):
        _run_git(repo, ["worktree", "add", str(worktree_path), repair_branch])
    else:
        _run_git(repo, ["worktree", "add", "-b", repair_branch, str(worktree_path), base_branch])

    return WorktreeInfo(
        repo_path=str(repo),
        worktree_path=str(worktree_path),
        repair_branch=repair_branch,
        base_branch=base_branch,
    )


def remove_repair_worktree(worktree_path: str | Path) -> None:
    path = Path(worktree_path)
    if not path.exists():
        return
    repo_path = path.parent.parent
    try:
        _run_git(repo_path, ["worktree", "remove", str(path), "--force"])
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
        append_audit_event("git_worktree_remove_fallback", None, {"worktree_path": str(path)})


def delete_local_branch(branch: str, repo_path: str | Path = ".") -> None:
    assert_safe_cleanup_branch(branch)
    _run_git(Path(repo_path).resolve(), ["branch", "-D", branch])


def delete_remote_branch(branch: str, repo_path: str | Path = ".", remote: str = "origin") -> None:
    assert_safe_cleanup_branch(branch)
    _run_git(Path(repo_path).resolve(), ["push", remote, "--delete", branch])


def git_commit_all(worktree_path: str | Path, message: str) -> str:
    worktree = Path(worktree_path).resolve()
    _run_git(worktree, ["add", "."])
    result = _run_git(worktree, ["commit", "-m", message])
    sha_result = _run_git(worktree, ["rev-parse", "HEAD"])
    return sha_result.stdout.strip()


def git_push_branch(worktree_path: str | Path, branch: str, remote: str = "origin") -> None:
    worktree = Path(worktree_path).resolve()
    _run_git(worktree, ["push", "-u", remote, branch])


def get_git_diff(worktree_path: str | Path) -> str:
    worktree = Path(worktree_path).resolve()
    result = subprocess.run(
        ["git", "diff"],
        cwd=str(worktree),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout
