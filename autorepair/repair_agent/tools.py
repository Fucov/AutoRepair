from __future__ import annotations

import re
import subprocess
from pathlib import Path

from autorepair.repair_agent.safety import (
    is_sensitive_path,
    resolve_worktree_path,
    validate_test_command,
)
from autorepair.repair_agent.schemas import ToolResult


class MiniRepairTools:
    def __init__(self, worktree_path: str) -> None:
        self.worktree_path = worktree_path
        self._read_files: set[str] = set()
        self.finish_reason: str | None = None

    def _rel(self, abs_path: Path) -> str:
        return str(abs_path.relative_to(Path(self.worktree_path))).replace("\\", "/")

    def read_file(self, path: str, line_range: str | None = None) -> ToolResult:
        if is_sensitive_path(path):
            return ToolResult(tool="read_file", ok=False, output="", error=f"拒绝访问敏感路径: {path}")

        target = resolve_worktree_path(self.worktree_path, path)
        if target is None:
            return ToolResult(tool="read_file", ok=False, output="", error=f"路径越界: {path}")

        if not target.exists():
            return ToolResult(tool="read_file", ok=False, output="", error=f"文件不存在: {path}")

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(tool="read_file", ok=False, output="", error=f"读取失败: {e}")

        lines = content.splitlines(keepends=True)

        if line_range:
            parts = line_range.split("-")
            start = max(int(parts[0]), 1)
            end = min(int(parts[1]), len(lines)) if len(parts) > 1 else start
            numbered = []
            for i in range(start - 1, end):
                numbered.append(f"{i + 1}: {lines[i].rstrip()}")
            output = "\n".join(numbered)
        else:
            numbered = []
            for i, line in enumerate(lines):
                numbered.append(f"{i + 1}: {line.rstrip()}")
            output = "\n".join(numbered)

        self._read_files.add(path)
        return ToolResult(tool="read_file", ok=True, output=output)

    def get_file_excerpt(self, path: str, line: int, context: int = 30) -> ToolResult:
        lo = max(1, line - context)
        hi = line + context
        return self.read_file(path, line_range=f"{lo}-{hi}")

    def search_text(self, query: str, file_glob: str | None = None, max_results: int = 30) -> ToolResult:
        wt = Path(self.worktree_path)
        results: list[str] = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for fpath in wt.rglob(file_glob or "*.py"):
            rel = fpath.relative_to(wt)
            rel_str = str(rel).replace("\\", "/")

            if "/.git/" in rel_str or rel_str.startswith(".git"):
                continue
            if is_sensitive_path(rel_str):
                continue

            try:
                content = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    results.append(f"{rel_str}:{i}: {line.rstrip()}")
                    if len(results) >= max_results:
                        return ToolResult(tool="search_text", ok=True, output="\n".join(results))

        return ToolResult(tool="search_text", ok=True, output="\n".join(results) if results else "(无匹配结果)")

    def run_tests(self, command: str, timeout: int = 120) -> ToolResult:
        if not validate_test_command(command):
            return ToolResult(
                tool="run_tests", ok=False, output="",
                error=f"拒绝执行非 pytest 命令: {command}",
            )

        try:
            result = subprocess.run(
                command,
                cwd=self.worktree_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout + ("\n" + result.stderr if result.stderr else "")
            return ToolResult(
                tool="run_tests",
                ok=result.returncode == 0,
                output=output.strip(),
                error=None if result.returncode == 0 else f"exit code {result.returncode}",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool="run_tests", ok=False, output="",
                error=f"测试超时 ({timeout}s)",
            )
        except Exception as e:
            return ToolResult(tool="run_tests", ok=False, output="", error=str(e))

    def apply_replace(self, path: str, old: str, new: str) -> ToolResult:
        if path not in self._read_files:
            return ToolResult(
                tool="apply_replace", ok=False, output="",
                error=f"请先 read_file('{path}') 再修改",
            )

        target = resolve_worktree_path(self.worktree_path, path)
        if target is None or not target.exists():
            return ToolResult(tool="apply_replace", ok=False, output="", error=f"文件不存在: {path}")

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(tool="apply_replace", ok=False, output="", error=f"读取失败: {e}")

        count = content.count(old)
        if count == 0:
            return ToolResult(
                tool="apply_replace", ok=False, output="",
                error="old 不存在于文件中，请重新 read_file 确认最新内容",
            )
        if count > 1:
            return ToolResult(
                tool="apply_replace", ok=False, output="",
                error=f"old 出现 {count} 次，需更多上下文使其唯一",
            )

        new_content = content.replace(old, new, 1)
        target.write_text(new_content, encoding="utf-8")
        return ToolResult(tool="apply_replace", ok=True, output="替换成功", changed=True)

    def rewrite_file(self, path: str, content: str) -> ToolResult:
        if path not in self._read_files:
            return ToolResult(
                tool="rewrite_file", ok=False, output="",
                error=f"请先 read_file('{path}') 再重写",
            )
        if not content:
            return ToolResult(
                tool="rewrite_file", ok=False, output="",
                error="content 不能为空",
            )

        target = resolve_worktree_path(self.worktree_path, path)
        if target is None:
            return ToolResult(tool="rewrite_file", ok=False, output="", error=f"路径越界: {path}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(tool="rewrite_file", ok=True, output="重写成功", changed=True)

    def git_diff(self) -> ToolResult:
        try:
            result = subprocess.run(
                ["git", "diff"],
                cwd=self.worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            return ToolResult(
                tool="git_diff",
                ok=True,
                output=result.stdout if result.stdout else "(无变更)",
            )
        except Exception as e:
            return ToolResult(tool="git_diff", ok=False, output="", error=str(e))

    def finish(self, status: str, summary: str) -> ToolResult:
        self.finish_reason = status
        return ToolResult(
            tool="finish",
            ok=True,
            output=f"Agent 结束: status={status}, summary={summary}",
        )
