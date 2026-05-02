import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch
from autorepair.repair.patch_applier import apply_patch_plan
from autorepair.repair.patch_schema import PatchPlan, FilePatch


def test_patch_applier_forbids_modifying_env_file():
    """FilePatch validator 拒绝 .env 路径，这是第一道安全防线"""
    import pydantic
    with pytest.raises(pydantic.ValidationError, match=r"\.env"):
        FilePatch(path=".env", operation="replace", old="A", new="B")


def test_patch_applier_fails_when_old_not_found():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write("def foo():\n    pass\n")
        temp_path = f.name
    
    try:
        worktree = str(Path(temp_path).parent)
        plan = PatchPlan(
            summary="test",
            files=[FilePatch(
                path=Path(temp_path).name,
                operation="replace",
                old="def nonexistent():",
                new="def new():\n    pass"
            )],
            tests_to_run=["pytest -q"],
            risk_level="low",
            confidence=0.9
        )
        result = apply_patch_plan(plan, worktree)
        assert result.ok is False
        assert "not found" in (result.error or "").lower()
    finally:
        Path(temp_path).unlink()


def test_patch_applier_fails_when_old_appears_multiple_times():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
        f.write("x = 1\nx = 2\nx = 3\n")
        temp_path = f.name
    
    try:
        worktree = str(Path(temp_path).parent)
        plan = PatchPlan(
            summary="test",
            files=[FilePatch(
                path=Path(temp_path).name,
                operation="replace",
                old="x = ",
                new="y = "
            )],
            tests_to_run=["pytest -q"],
            risk_level="low",
            confidence=0.9
        )
        result = apply_patch_plan(plan, worktree)
        assert result.ok is False
        assert "ambiguous" in (result.error or "").lower()
    finally:
        Path(temp_path).unlink()
