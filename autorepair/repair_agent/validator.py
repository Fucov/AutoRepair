from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.schemas import RepairAgentContext
from autorepair.repair_agent.spec_builder import RepairSpec

logger = logging.getLogger(__name__)

MAX_OUTPUT_LENGTH = 1500


class FailureSummary(BaseModel):
    failed_command: str
    failure_type: str
    relevant_output: str
    violated_spec_item: str = ""


class ValidationPlan(BaseModel):
    reproduce_command: str | None = None
    target_commands: list[str] = Field(default_factory=list)
    related_commands: list[str] = Field(default_factory=list)
    full_command: str = "pytest -q"


class ValidationResult(BaseModel):
    phase: Literal["before", "after"]
    reproduce_ok: bool | None = None
    target_ok: bool | None = None
    related_ok: bool | None = None
    full_ok: bool | None = None
    failure_summary: FailureSummary | None = None


def build_validation_plan(
    case: RepairCase,
    spec: RepairSpec,
    context: RepairAgentContext,
) -> ValidationPlan:
    target_cmds = []
    for test in case.target_tests:
        target_cmds.append(_pytest_command(test, include_agent_target=True))

    if not target_cmds and context.target_test_command:
        target_cmds = [context.target_test_command]

    related_cmds = []
    for test in case.regression_tests:
        related_cmds.append(_pytest_command(test, include_agent_target=True))

    return ValidationPlan(
        reproduce_command=target_cmds[0] if target_cmds else None,
        target_commands=target_cmds or ["pytest -q"],
        related_commands=related_cmds,
        full_command=context.full_test_command or "pytest -q",
    )


def _pytest_command(test: str, include_agent_target: bool = False) -> str:
    command = f"pytest -q {test}"
    if include_agent_target and "-m " not in command:
        command += " -m agent_target"
    return command


def run_validation_plan(
    tools,
    plan: ValidationPlan,
    phase: Literal["before", "after"],
    spec: RepairSpec | None = None,
) -> ValidationResult:
    if phase == "before":
        return _run_before_phase(tools, plan, spec)
    return _run_after_phase(tools, plan, spec)


def _run_before_phase(tools, plan: ValidationPlan, spec: RepairSpec | None) -> ValidationResult:
    if plan.reproduce_command:
        result = tools.run_tests(plan.reproduce_command)
        return ValidationResult(
            phase="before",
            reproduce_ok=result.ok,
            target_ok=result.ok,
            failure_summary=None if result.ok else FailureSummary(
                failed_command=plan.reproduce_command,
                failure_type="test_failed",
                relevant_output=_truncate(result.output or result.error or ""),
                violated_spec_item=_find_violated_spec(spec) if spec else "",
            ),
        )

    if plan.target_commands:
        cmd = plan.target_commands[0]
        result = tools.run_tests(cmd)
        return ValidationResult(
            phase="before",
            target_ok=result.ok,
            failure_summary=None if result.ok else FailureSummary(
                failed_command=cmd,
                failure_type="test_failed",
                relevant_output=_truncate(result.output or result.error or ""),
                violated_spec_item=_find_violated_spec(spec) if spec else "",
            ),
        )

    return ValidationResult(phase="before", target_ok=False)


def _run_after_phase(tools, plan: ValidationPlan, spec: RepairSpec | None) -> ValidationResult:
    target_ok = True
    failure: FailureSummary | None = None

    for cmd in plan.target_commands:
        result = tools.run_tests(cmd)
        if not result.ok:
            target_ok = False
            failure = FailureSummary(
                failed_command=cmd,
                failure_type="test_failed",
                relevant_output=_truncate(result.output or result.error or ""),
                violated_spec_item=_find_violated_spec(spec) if spec else "",
            )
            return ValidationResult(
                phase="after",
                target_ok=False,
                related_ok=None,
                full_ok=None,
                failure_summary=failure,
            )

    related_ok = True
    for cmd in plan.related_commands:
        result = tools.run_tests(cmd)
        if not result.ok:
            related_ok = False
            failure = FailureSummary(
                failed_command=cmd,
                failure_type="regression_failed",
                relevant_output=_truncate(result.output or result.error or ""),
                violated_spec_item="回归测试失败",
            )
            return ValidationResult(
                phase="after",
                target_ok=True,
                related_ok=False,
                full_ok=None,
                failure_summary=failure,
            )

    full_result = tools.run_tests(plan.full_command)
    if not full_result.ok:
        failure = FailureSummary(
            failed_command=plan.full_command,
            failure_type="full_test_failed",
            relevant_output=_truncate(full_result.output or full_result.error or ""),
            violated_spec_item="全量测试失败",
        )

    return ValidationResult(
        phase="after",
        target_ok=True,
        related_ok=related_ok,
        full_ok=full_result.ok,
        failure_summary=failure,
    )


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_LENGTH:
        return text
    return text[:MAX_OUTPUT_LENGTH] + "...(截断)"


def _find_violated_spec(spec: RepairSpec | None) -> str:
    if not spec:
        return ""
    parts = []
    if spec.postconditions:
        parts.append("postconditions: " + "; ".join(spec.postconditions[:3]))
    if spec.invariants:
        parts.append("invariants: " + "; ".join(spec.invariants[:2]))
    return " | ".join(parts)
