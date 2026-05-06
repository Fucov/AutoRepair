from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    ok: bool
    output: str
    error: str | None = None
    changed: bool = False


class AgentStep(BaseModel):
    step_index: int
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    note: str | None = None


class RepairAgentContext(BaseModel):
    job_id: str
    incident_id: str
    issue_number: int | None = None
    service_name: str = "unknown"
    worktree_path: str
    repo_path: str = ""
    error_type: str | None = None
    error_message: str | None = None
    suspected_file: str | None = None
    line_no: int | None = None
    raw_traceback: str | None = None
    issue_body: str | None = None
    target_test_command: str | None = None
    full_test_command: str = "pytest -q"


class RepairAgentResult(BaseModel):
    ok: bool
    status: Literal[
        "fixed",
        "test_failed",
        "not_reproducible",
        "unsafe_patch",
        "needs_human",
        "agent_error",
    ]
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    target_test_passed: bool = False
    full_test_passed: bool = False
    diff: str | None = None
    transcript_path: str | None = None
    error: str | None = None


class AgentPhase(str, Enum):
    REPRODUCE = "REPRODUCE"
    UNDERSTAND = "UNDERSTAND"
    PLAN = "PLAN"
    EDIT = "EDIT"
    VALIDATE = "VALIDATE"
    FINALIZE = "FINALIZE"


PHASE_BUDGETS: dict[AgentPhase, int] = {
    AgentPhase.REPRODUCE: 1,
    AgentPhase.UNDERSTAND: 3,
    AgentPhase.PLAN: 1,
    AgentPhase.EDIT: 3,
    AgentPhase.VALIDATE: 3,
    AgentPhase.FINALIZE: 1,
}


class RepairPlanLite(BaseModel):
    root_cause: str
    edit_files: list[str] = Field(default_factory=list)
    strategy: str
    spec_items_to_satisfy: list[str] = Field(default_factory=list)


class Checkpoint(BaseModel):
    phase: AgentPhase
    step_index: int
    file_snapshots: dict[str, str] = Field(default_factory=dict)
    diff: str | None = None
    target_test_passed: bool = False
