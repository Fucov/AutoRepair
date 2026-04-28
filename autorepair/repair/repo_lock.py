from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from autorepair.config import PROJECT_ROOT


DEFAULT_LOCK_DIR = PROJECT_ROOT / "autorepair" / "records" / "locks"


@dataclass
class RepoLock:
    repo_key: str
    lock_path: Path
    acquired: bool


def _lock_path_for(repo_key: str) -> Path:
    digest = hashlib.sha1(repo_key.encode("utf-8")).hexdigest()[:16]
    return DEFAULT_LOCK_DIR / f"repo_{digest}.lock"


@contextmanager
def acquire_repo_lock(repo_key: str):
    DEFAULT_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path_for(repo_key)
    fd: int | None = None
    acquired = False
    try:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n{repo_key}\n".encode("utf-8"))
            acquired = True
        except FileExistsError:
            acquired = False
        yield RepoLock(repo_key=repo_key, lock_path=lock_path, acquired=acquired)
    finally:
        if fd is not None:
            os.close(fd)
        if acquired:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
