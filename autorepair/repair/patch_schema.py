from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, validator


class FilePatch(BaseModel):
    path: str
    operation: Literal["replace"] = "replace"
    old: str
    new: str
    
    @validator("path")
    def validate_path_safety(cls, v: str) -> str:
        forbidden_patterns = [".env", ".git", "secret", "credential", "key", "password"]
        for pattern in forbidden_patterns:
            if pattern.lower() in v.lower():
                raise ValueError(f"Path {v} contains forbidden pattern: {pattern}")
        return v
    
    @validator("old", "new")
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("old and new content cannot be empty")
        return v


class PatchPlan(BaseModel):
    summary: str
    files: list[FilePatch] = Field(default_factory=list, max_items=5)
    tests_to_run: list[str] = Field(min_items=1)
    risk_level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    
    @validator("tests_to_run")
    def validate_test_commands(cls, v: list[str]) -> list[str]:
        for cmd in v:
            if not cmd.strip().startswith("pytest"):
                raise ValueError(f"Invalid test command: {cmd}. Only pytest commands are allowed.")
        return v


class PatchApplyResult(BaseModel):
    ok: bool
    changed_files: list[str] = Field(default_factory=list)
    error: str | None = None
