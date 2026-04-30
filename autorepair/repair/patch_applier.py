from __future__ import annotations
from pathlib import Path
from autorepair.repair.patch_schema import PatchPlan, PatchApplyResult


def apply_patch_plan(patch_plan: PatchPlan, worktree_path: str) -> PatchApplyResult:
    worktree = Path(worktree_path).resolve()
    changed_files: list[str] = []
    
    try:
        for file_patch in patch_plan.files:
            file_path = (worktree / file_patch.path).resolve()
            
            if not str(file_path).startswith(str(worktree)):
                return PatchApplyResult(
                    ok=False,
                    error=f"Path {file_patch.path} is outside of worktree directory"
                )
            
            forbidden_patterns = [".env", ".git", "secret", "credential", "key", "password"]
            for pattern in forbidden_patterns:
                if pattern.lower() in str(file_path).lower():
                    return PatchApplyResult(
                        ok=False,
                        error=f"Path {file_patch.path} contains forbidden pattern: {pattern}"
                    )
            
            if not file_path.exists() or not file_path.is_file():
                return PatchApplyResult(
                    ok=False,
                    error=f"File {file_patch.path} does not exist in worktree"
                )
            
            content = file_path.read_text(encoding="utf-8")
            
            occurrences = content.count(file_patch.old)
            if occurrences == 0:
                return PatchApplyResult(
                    ok=False,
                    error=f"Old content not found in {file_patch.path}"
                )
            if occurrences > 1:
                return PatchApplyResult(
                    ok=False,
                    error=f"Old content appears {occurrences} times in {file_patch.path}, ambiguous match"
                )
            
            new_content = content.replace(file_patch.old, file_patch.new, 1)
            
            file_path.write_text(new_content, encoding="utf-8")
            changed_files.append(file_patch.path)
        
        return PatchApplyResult(
            ok=True,
            changed_files=changed_files
        )
    
    except Exception as e:
        return PatchApplyResult(
            ok=False,
            error=f"Failed to apply patch: {str(e)}"
        )
