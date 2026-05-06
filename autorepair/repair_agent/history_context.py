from __future__ import annotations

import subprocess
from pydantic import BaseModel, Field


class HistoryContext(BaseModel):
    file: str
    recent_commits: list[str] = Field(default_factory=list)
    blame_around_line: str | None = None
    last_modifier_summary: str = ""


def collect_history_context(
    worktree_path: str,
    files: list[str],
    line_no: int | None = None,
) -> HistoryContext:
    if not files:
        return HistoryContext(file="")

    target_file = files[0]
    recent_commits = _git_log(worktree_path, target_file, n=5)
    blame_around_line = _git_blame(worktree_path, target_file, line_no)
    last_modifier_summary = _last_modifier_summary(worktree_path, target_file)

    return HistoryContext(
        file=target_file,
        recent_commits=recent_commits,
        blame_around_line=blame_around_line,
        last_modifier_summary=last_modifier_summary,
    )


def _git_log(worktree_path: str, file_path: str, n: int = 5) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--oneline", "--", file_path],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return []
        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        return lines[:n]
    except Exception:
        return []


def _git_blame(worktree_path: str, file_path: str, line_no: int | None) -> str | None:
    if line_no is None:
        return None
    try:
        lo = max(1, line_no - 5)
        hi = line_no + 5
        range_str = f"{lo},{hi}"
        result = subprocess.run(
            ["git", "blame", f"-L{range_str}", "--porcelain", file_path],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().splitlines()
        formatted = []
        for line in lines[:10]:
            if line.startswith("summary"):
                formatted.append(line.split(" ", 1)[1] if " " in line else line)
            elif not line.startswith("\t") and len(line) > 40 and " " in line:
                pass
        return "\n".join(formatted) if formatted else None
    except Exception:
        return None


def _last_modifier_summary(worktree_path: str, file_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", "--", file_path],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()[:500]
    except Exception:
        return ""