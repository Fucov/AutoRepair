from __future__ import annotations

from pathlib import Path

SENSITIVE_FILENAMES = {
    ".env",
    ".gitignore",
    ".git",
    "secrets.yaml",
    "secrets.yml",
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
}

SENSITIVE_SUBSTRINGS_IN_PATH = [
    "/.git/",
    "/.env",
    "/secrets/",
    "/credentials",
]


def is_sensitive_path(path: str) -> bool:
    path_norm = path.replace("\\", "/")
    if path_norm in (".git", ".env"):
        return True
    for pat in SENSITIVE_SUBSTRINGS_IN_PATH:
        if pat in path_norm:
            return True
    name = Path(path).name
    if name in SENSITIVE_FILENAMES:
        return True
    return False


def is_safe_relative_path(worktree_path: str, relative_path: str) -> bool:
    try:
        wt = Path(worktree_path).resolve()
        target = (wt / relative_path).resolve()
        return str(target).startswith(str(wt))
    except (ValueError, OSError):
        return False


def resolve_worktree_path(worktree_path: str, relative_path: str) -> Path | None:
    if is_sensitive_path(relative_path):
        return None
    if not is_safe_relative_path(worktree_path, relative_path):
        return None
    wt = Path(worktree_path).resolve()
    target = (wt / relative_path).resolve()
    return target


def validate_test_command(command: str) -> bool:
    if not command or not command.strip():
        return False
    cmd = command.strip()
    if cmd.startswith("pytest"):
        return True
    if cmd.startswith("python -m pytest"):
        return True
    return False
