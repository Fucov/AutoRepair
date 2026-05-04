from __future__ import annotations

import logging
from difflib import SequenceMatcher
from pathlib import Path

from autorepair.repair.patch_schema import PatchPlan, PatchApplyResult

logger = logging.getLogger(__name__)


def _normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines()]


def _fuzzy_find(content: str, old: str) -> int | None:
    norm_content = "\n".join(_normalize_lines(content))
    norm_old = "\n".join(_normalize_lines(old))
    idx = norm_content.find(norm_old)
    if idx >= 0:
        lines_before = norm_content[:idx].count("\n")
        real_lines = content.splitlines()
        result = 0
        for i in range(lines_before):
            result += len(real_lines[i]) + 1
        return result
    return None


def _find_similar_segment(content: str, old: str, max_lines: int = 5) -> str | None:
    old_lines = old.strip().splitlines()
    if not old_lines:
        return None
    content_lines = content.splitlines()
    best_score = 0.0
    best_start = 0
    window = len(old_lines)
    for i in range(max(0, len(content_lines) - window + 1)):
        candidate = "\n".join(content_lines[i : i + window])
        score = SequenceMatcher(None, old.strip(), candidate.strip()).ratio()
        if score > best_score:
            best_score = score
            best_start = i
    if best_score >= 0.5:
        end = min(best_start + max_lines, len(content_lines))
        return "\n".join(content_lines[best_start:end])
    return None


def apply_patch_plan(patch_plan: PatchPlan, worktree_path: str) -> PatchApplyResult:
    if not patch_plan.files:
        return PatchApplyResult(ok=True, changed_files=[])

    worktree = Path(worktree_path).resolve()
    changed_files: list[str] = []
    errors: list[str] = []

    for file_patch in patch_plan.files:
        file_path = (worktree / file_patch.path).resolve()

        if not str(file_path).startswith(str(worktree)):
            errors.append(f"路径 {file_patch.path} 超出 worktree 目录")
            continue

        forbidden_patterns = [".env", ".git", "secret", "credential", "key", "password"]
        path_lower = str(file_path).lower()
        forbidden_hit = False
        for pattern in forbidden_patterns:
            if pattern.lower() in path_lower:
                errors.append(f"路径 {file_patch.path} 包含禁止模式: {pattern}")
                forbidden_hit = True
                break
        if forbidden_hit:
            continue

        if not file_path.exists() or not file_path.is_file():
            errors.append(f"文件 {file_patch.path} 在 worktree 中不存在")
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"读取文件 {file_patch.path} 失败: {e}")
            continue

        occurrences = content.count(file_patch.old)
        if occurrences == 0:
            fuzzy_idx = _fuzzy_find(content, file_patch.old)
            if fuzzy_idx is not None:
                norm_old = "\n".join(_normalize_lines(file_patch.old))
                norm_new = "\n".join(_normalize_lines(file_patch.new))
                norm_content = "\n".join(_normalize_lines(content))
                new_norm_content = norm_content.replace(norm_old, norm_new, 1)
                old_lines = content.splitlines()
                norm_new_lines = new_norm_content.splitlines()
                if len(norm_new_lines) >= len(old_lines):
                    file_path.write_text(new_norm_content, encoding="utf-8")
                    changed_files.append(file_patch.path)
                    logger.warning(f"文件 {file_patch.path} 使用模糊匹配完成替换")
                    continue

            similar = _find_similar_segment(content, file_patch.old)
            old_preview = file_patch.old[:200]
            detail = f"在 {file_patch.path} 中未找到 old 内容匹配。\n期望内容(前200字符): {old_preview}"
            if similar:
                detail += f"\n文件中最相似的内容:\n{similar}"
            errors.append(detail)
            continue

        if occurrences > 1:
            errors.append(f"old 内容在 {file_patch.path} 中出现 {occurrences} 次，存在歧义匹配")
            continue

        new_content = content.replace(file_patch.old, file_patch.new, 1)
        file_path.write_text(new_content, encoding="utf-8")
        changed_files.append(file_patch.path)

    if errors and not changed_files:
        return PatchApplyResult(ok=False, error="; ".join(errors))

    if errors:
        logger.warning(f"部分补丁应用失败: {errors}")

    return PatchApplyResult(ok=True, changed_files=changed_files)
