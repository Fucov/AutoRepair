from __future__ import annotations
import subprocess
import time
from pathlib import Path
from pydantic import BaseModel


class CommandResult(BaseModel):
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


def run_command_in_worktree(command: str, worktree_path: str, timeout: int = 120) -> CommandResult:
    worktree = Path(worktree_path).resolve()
    
    if not command.strip().startswith("pytest"):
        raise ValueError(f"Invalid command: {command}. Only pytest commands are allowed.")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            cwd=worktree,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        
        duration = time.time() - start_time
        
        return CommandResult(
            command=command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=round(duration, 2)
        )
        
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        return CommandResult(
            command=command,
            returncode=-1,
            stdout=e.stdout.decode("utf-8", errors="replace") if e.stdout else "",
            stderr=e.stderr.decode("utf-8", errors="replace") if e.stderr else f"Command timed out after {timeout} seconds",
            duration_seconds=round(duration, 2)
        )
    except Exception as e:
        duration = time.time() - start_time
        return CommandResult(
            command=command,
            returncode=-2,
            stdout="",
            stderr=str(e),
            duration_seconds=round(duration, 2)
        )
