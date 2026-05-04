from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from autorepair.repair.schemas import RepairJob
from autorepair.schemas import Incident


class TracebackFrame(BaseModel):
    file_path: str
    line_no: int
    function: str
    code_line: str | None = None


class TracebackInfo(BaseModel):
    error_type: str
    error_message: str
    frames: list[TracebackFrame]
    project_files: list[str]
    suspected_file: str | None = None
    suspected_line: int | None = None


class RepairContext(BaseModel):
    incident_id: str
    issue_number: int
    service_name: str
    error_type: str
    error_message: str
    suspected_file: str | None
    line_no: int | None
    raw_traceback: str
    target_test_command: str
    full_test_command: str
    code_snippets: dict[str, str]
    existing_tests: dict[str, str]
    project_structure: str
    dependencies: str
    all_traceback_files: list[str]


_TRACEBACK_FILE_RE = re.compile(
    r'^\s*File "(.+?)", line (\d+), in (\S+)',
    re.MULTILINE,
)
_TRACEBACK_ERROR_RE = re.compile(
    r"^(\w+(?:\.\w+)*(?:Error|Exception|Warning))\s*:\s*(.+)$",
    re.MULTILINE,
)
_TRACEBACK_CODE_RE = re.compile(r"^\s{4}.+$", re.MULTILINE)


def _parse_traceback(raw: str, worktree: Path) -> TracebackInfo:
    if not raw or not raw.strip():
        return TracebackInfo(
            error_type="UnknownError",
            error_message="",
            frames=[],
            project_files=[],
            suspected_file=None,
            suspected_line=None,
        )

    frames: list[TracebackFrame] = []
    project_files: list[str] = []
    lines = list(raw.splitlines())
    worktree_str = str(worktree.resolve())

    i = 0
    while i < len(lines):
        m = _TRACEBACK_FILE_RE.match(lines[i])
        if m:
            fpath, line_str, func = m.group(1), m.group(2), m.group(3)
            code_line = None
            if i + 1 < len(lines) and lines[i + 1].startswith("    "):
                code_line = lines[i + 1].strip()
            frames.append(TracebackFrame(
                file_path=fpath,
                line_no=int(line_str),
                function=func,
                code_line=code_line,
            ))
            try:
                resolved = Path(fpath).resolve()
                if str(resolved).startswith(worktree_str):
                    rel = str(resolved.relative_to(worktree))
                    rel = rel.replace("\\", "/")
                    if rel not in project_files:
                        project_files.append(rel)
            except (ValueError, OSError):
                pass
        i += 1

    error_type = "UnknownError"
    error_message = ""
    for line in reversed(lines):
        em = _TRACEBACK_ERROR_RE.search(line)
        if em:
            error_type = em.group(1)
            error_message = em.group(2).strip()
            break

    suspected_file = project_files[0] if project_files else None
    suspected_line = None
    if frames:
        for frame in reversed([frame for frame in frames if frame.file_path]):
            try:
                resolved = Path(frame.file_path).resolve()
                if str(resolved).startswith(worktree_str):
                    suspected_file = str(resolved.relative_to(worktree)).replace("\\", "/")
                    suspected_line = frame.line_no
                    break
            except (ValueError, OSError):
                continue

    return TracebackInfo(
        error_type=error_type,
        error_message=error_message,
        frames=frames,
        project_files=project_files,
        suspected_file=suspected_file,
        suspected_line=suspected_line,
    )


def _read_code_context(worktree: Path, rel_file: str, center_line: int | None, window: int = 50) -> str:
    file_path = worktree / rel_file
    if not file_path.exists() or not file_path.is_file():
        return ""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    if center_line and 1 <= center_line <= len(lines):
        start = max(0, center_line - 1 - window)
        end = min(len(lines), center_line - 1 + window)
    else:
        start = 0
        end = min(len(lines), 200)
    return "\n".join(lines[start:end])


def _infer_target_test(worktree: Path, suspected_file: str | None, incident: Incident) -> str:
    tests_dir = worktree / "demo_service" / "tests"
    if not tests_dir.is_dir():
        tests_dir = worktree / "tests"
    if not tests_dir.is_dir():
        return "pytest -q"

    all_test_files = sorted(tests_dir.glob("test_*.py"))
    if not all_test_files:
        return "pytest -q"

    agent_target_tests: list[Path] = []
    for tf in all_test_files:
        try:
            content = tf.read_text(encoding="utf-8")
            if "agent_target" in content:
                agent_target_tests.append(tf)
        except Exception:
            pass

    related_tests: list[Path] = []
    if suspected_file:
        stem = Path(suspected_file).stem
        for tf in all_test_files:
            if stem in tf.name:
                related_tests.append(tf)

    def _rel(p: Path) -> str:
        return str(p.relative_to(worktree)).replace("\\", "/")

    if related_tests:
        for rt in related_tests:
            if rt in agent_target_tests:
                return f"pytest -q {_rel(rt)} -m agent_target"
        return f"pytest -q {' '.join(_rel(r) for r in related_tests)}"

    if agent_target_tests:
        return f"pytest -q {' '.join(_rel(t) for t in agent_target_tests)} -m agent_target"

    return "pytest -q"


def _collect_project_structure(worktree: Path, max_depth: int = 2) -> str:
    lines: list[str] = []

    def _walk(dir_path: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith(".") or entry.name in {"__pycache__", "node_modules", ".worktrees", ".git"}:
                continue
            lines.append(f"{prefix}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                _walk(entry, prefix + "  ", depth + 1)

    _walk(worktree, "", 0)
    return "\n".join(lines)


def _collect_dependencies(worktree: Path) -> str:
    for fname in ("requirements.txt", "pyproject.toml", "setup.cfg", "Pipfile"):
        dep_file = worktree / fname
        if dep_file.exists() and dep_file.is_file():
            try:
                content = dep_file.read_text(encoding="utf-8")
                return f"# {fname}\n{content}"
            except Exception:
                continue
    return "# No dependency file found"


def collect_repair_context(job: RepairJob, incident: Incident, worktree_path: str) -> RepairContext:
    worktree = Path(worktree_path).resolve()
    tb_info = _parse_traceback(incident.raw_traceback, worktree)

    error_type = incident.error_summary.error_type or tb_info.error_type
    error_message = incident.error_summary.message or tb_info.error_message
    suspected_file = incident.error_summary.suspected_file or tb_info.suspected_file
    line_no = incident.error_summary.line_no or tb_info.suspected_line

    code_snippets: dict[str, str] = {}
    if suspected_file:
        snippet = _read_code_context(worktree, suspected_file, line_no)
        if snippet:
            code_snippets[suspected_file] = snippet

    for fpath in tb_info.project_files:
        if fpath not in code_snippets:
            for frame in tb_info.frames:
                try:
                    resolved = Path(frame.file_path).resolve()
                    rel = str(resolved.relative_to(worktree)).replace("\\", "/")
                    if rel == fpath:
                        snippet = _read_code_context(worktree, fpath, frame.line_no)
                        if snippet:
                            code_snippets[fpath] = snippet
                        break
                except (ValueError, OSError):
                    continue
            else:
                snippet = _read_code_context(worktree, fpath, None)
                if snippet:
                    code_snippets[fpath] = snippet

    target_test_cmd = _infer_target_test(worktree, suspected_file, incident)
    full_test_cmd = "pytest -q"

    existing_tests: dict[str, str] = {}
    tests_dir = worktree / "demo_service" / "tests"
    if not tests_dir.is_dir():
        tests_dir = worktree / "tests"
    if tests_dir.is_dir():
        for tf in sorted(tests_dir.glob("test_*.py")):
            rel = str(tf.relative_to(worktree)).replace("\\", "/")
            try:
                existing_tests[rel] = tf.read_text(encoding="utf-8")
            except Exception:
                pass

    project_structure = _collect_project_structure(worktree)
    dependencies = _collect_dependencies(worktree)

    return RepairContext(
        incident_id=job.incident_id,
        issue_number=job.issue_number,
        service_name=incident.service_name or incident.service or "unknown",
        error_type=error_type,
        error_message=error_message,
        suspected_file=suspected_file,
        line_no=line_no,
        raw_traceback=incident.raw_traceback,
        target_test_command=target_test_cmd,
        full_test_command=full_test_cmd,
        code_snippets=code_snippets,
        existing_tests=existing_tests,
        project_structure=project_structure,
        dependencies=dependencies,
        all_traceback_files=tb_info.project_files,
    )
