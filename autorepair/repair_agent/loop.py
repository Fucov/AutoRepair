from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from autorepair.adapters.llm_client import LLMClient
from autorepair.repair_agent.history_context import HistoryContext
from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.prompts import (
    build_initial_user_prompt,
    build_next_step_prompt,
    build_repair_agent_system_prompt,
    build_spec_violation_feedback,
)
from autorepair.repair_agent.schemas import (
    AgentPhase,
    AgentStep,
    Checkpoint,
    PHASE_BUDGETS,
    RepairAgentContext,
    RepairAgentResult,
    RepairPlanLite,
    ToolCall,
    ToolResult,
)
from autorepair.repair_agent.spec_builder import RepairSpec
from autorepair.repair_agent.tools import MiniRepairTools
from autorepair.repair_agent.transcript_store import save_repair_transcript
from autorepair.repair_agent.validator import (
    ValidationPlan,
    ValidationResult,
    run_validation_plan,
)

logger = logging.getLogger(__name__)


class MiniRepairAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        max_steps: int = 8,
        max_retries: int = 2,
    ) -> None:
        self.llm = llm_client
        self.max_steps = max_steps
        self.max_retries = max_retries

    def run(self, context: RepairAgentContext) -> RepairAgentResult:
        tools = MiniRepairTools(context.worktree_path)
        steps: list[AgentStep] = []
        step_idx = 0
        retry_count = 0

        test_output = ""
        if context.target_test_command:
            initial_test = tools.run_tests(context.target_test_command)
            test_output = initial_test.output or initial_test.error or ""

            if initial_test.ok:
                result = RepairAgentResult(
                    ok=True,
                    status="not_reproducible",
                    summary="目标测试已通过，无法复现问题",
                    tests_run=[context.target_test_command],
                    target_test_passed=True,
                )
                _save(context.job_id, steps, result)
                return result

        code_excerpt = None
        if context.suspected_file and context.line_no:
            r = tools.get_file_excerpt(context.suspected_file, context.line_no)
            if r.ok:
                code_excerpt = r.output

        system_prompt = build_repair_agent_system_prompt()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_initial_user_prompt(context, test_output, code_excerpt),
            },
        ]

        last_result = ToolResult(tool="init", ok=True, output=test_output)

        while step_idx < self.max_steps:
            try:
                tool_call = self._call_llm(messages)
            except Exception as e:
                logger.error("LLM 调用失败 step=%d: %s", step_idx, e)
                result = RepairAgentResult(
                    ok=False,
                    status="agent_error",
                    summary=f"LLM 调用失败: {e}",
                    error=str(e),
                )
                _save(context.job_id, steps, result)
                return result

            step = AgentStep(step_index=step_idx, tool_call=tool_call)
            steps.append(step)

            if tool_call.tool == "finish":
                status = tool_call.args.get("status", "needs_human")
                summary = tool_call.args.get("summary", "")
                diff = None
                diff_r = tools.git_diff()
                if diff_r.ok:
                    diff = diff_r.output

                result = RepairAgentResult(
                    ok=(status == "fixed"),
                    status=status,
                    summary=summary,
                    diff=diff,
                    target_test_passed=status == "fixed",
                    full_test_passed=status == "fixed",
                )
                _save(context.job_id, steps, result)
                return result

            tr = self._dispatch_tool(tools, tool_call)
            step.tool_result = tr
            steps[-1] = step

            if tool_call.tool == "run_tests" and not tr.ok:
                retry_count += 1
                if retry_count >= self.max_retries:
                    diff = None
                    diff_r = tools.git_diff()
                    if diff_r.ok:
                        diff = diff_r.output
                    result = RepairAgentResult(
                        ok=False,
                        status="test_failed",
                        summary=f"超过最大重试次数 ({self.max_retries})，测试仍失败",
                        diff=diff,
                        tests_run=[context.target_test_command or "", context.full_test_command],
                        target_test_passed=False,
                        full_test_passed=False,
                    )
                    _save(context.job_id, steps, result)
                    return result

            if tool_call.tool == "run_tests" and tr.ok:
                retry_count = 0

            diff = None
            if tr.changed:
                diff_r = tools.git_diff()
                if diff_r.ok:
                    diff = diff_r.output

            next_prompt = build_next_step_prompt(tr, diff)
            messages.append({"role": "assistant", "content": str(tool_call.model_dump())})
            messages.append({"role": "user", "content": next_prompt})

            step_idx += 1

        diff = None
        diff_r = tools.git_diff()
        if diff_r.ok:
            diff = diff_r.output
        result = RepairAgentResult(
            ok=False,
            status="test_failed",
            summary=f"达到最大步骤数 ({self.max_steps})，Agent 未完成修复",
            diff=diff,
        )
        _save(context.job_id, steps, result)
        return result

    def run_spec_guided(
        self,
        context: RepairAgentContext,
        repair_case: RepairCase,
        repair_spec: RepairSpec,
        skills: list[Any],
        validation_plan: ValidationPlan,
        history_context: HistoryContext | None = None,
    ) -> RepairAgentResult:
        tools = MiniRepairTools(
            context.worktree_path,
            allowed_files=set(repair_case.allowed_files),
            forbidden_files=set(repair_case.forbidden_files),
        )
        steps: list[AgentStep] = []
        step_idx = 0
        phase = AgentPhase.REPRODUCE
        phase_steps = 0
        checkpoint: Checkpoint | None = None
        consecutive_no_improve = 0
        total_budget = sum(PHASE_BUDGETS.values())

        test_output = ""
        before_result = run_validation_plan(tools, validation_plan, "before", repair_spec)
        if before_result.target_ok:
            result = RepairAgentResult(
                ok=True,
                status="not_reproducible",
                summary="目标测试已通过，无法复现问题",
                tests_run=validation_plan.target_commands,
                target_test_passed=True,
            )
            _save(context.job_id, steps, result)
            return result
        test_output = before_result.failure_summary.relevant_output if before_result.failure_summary else ""

        code_excerpt = None
        if context.suspected_file and context.line_no:
            r = tools.get_file_excerpt(context.suspected_file, context.line_no)
            if r.ok:
                code_excerpt = r.output

        system_prompt = build_repair_agent_system_prompt()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_initial_user_prompt(
                    context, test_output, code_excerpt,
                    repair_case=repair_case,
                    repair_spec=repair_spec,
                    skills=skills,
                    validation_plan=validation_plan,
                    history_context=history_context,
                ),
            },
        ]

        phase = AgentPhase.UNDERSTAND
        phase_steps = 0

        while step_idx < total_budget:
            if phase_steps >= PHASE_BUDGETS.get(phase, 3):
                phase, phase_steps = self._advance_phase(phase)
                if phase == AgentPhase.FINALIZE:
                    break
                continue

            try:
                tool_call = self._call_llm(messages)
            except Exception as e:
                logger.error("LLM 调用失败 step=%d phase=%s: %s", step_idx, phase.value, e)
                result = RepairAgentResult(
                    ok=False,
                    status="agent_error",
                    summary=f"LLM 调用失败 ({phase.value}): {e}",
                    error=str(e),
                )
                _save(context.job_id, steps, result)
                return result

            step = AgentStep(step_index=step_idx, tool_call=tool_call)
            steps.append(step)

            if tool_call.tool == "finish":
                status = tool_call.args.get("status", "needs_human")
                summary = tool_call.args.get("summary", "")
                diff_r = tools.git_diff()
                diff = diff_r.output if diff_r.ok else None
                result = RepairAgentResult(
                    ok=(status == "fixed"),
                    status=status,
                    summary=summary,
                    diff=diff,
                    target_test_passed=status == "fixed",
                    full_test_passed=status == "fixed",
                )
                _save(context.job_id, steps, result)
                return result

            if phase == AgentPhase.PLAN and tool_call.tool not in ("finish", "read_file", "search_text"):
                plan_content = tool_call.args.get("content", "") or tool_call.args.get("output", "")
                try:
                    RepairPlanLite.model_validate_json(plan_content) if isinstance(plan_content, str) and plan_content.startswith("{") else None
                except Exception:
                    pass

            if phase == AgentPhase.EDIT and checkpoint is None:
                checkpoint = self._save_checkpoint(tools, phase, step_idx, repair_case.allowed_files)

            if phase == AgentPhase.EDIT and tool_call.tool in ("apply_replace", "rewrite_file"):
                file_path = tool_call.args.get("path", "")
                if file_path not in repair_case.allowed_files:
                    tr = ToolResult(
                        tool=tool_call.tool, ok=False, output="",
                        error=f"不允许修改文件 {file_path}，allowed_files: {repair_case.allowed_files}",
                    )
                    step.tool_result = tr
                    steps[-1] = step
                    step_idx += 1
                    phase_steps += 1
                    messages.append({"role": "assistant", "content": str(tool_call.model_dump())})
                    messages.append({"role": "user", "content": f"文件 {file_path} 不在 allowed_files 中。只能修改: {repair_case.allowed_files}"})
                    continue

            tr = self._dispatch_tool(tools, tool_call)
            step.tool_result = tr
            steps[-1] = step

            if phase == AgentPhase.EDIT and tr.changed:
                diff_r = tools.git_diff()
                diff = diff_r.output if diff_r.ok else None
                next_prompt = build_next_step_prompt(tr, diff)
            elif phase == AgentPhase.EDIT and tool_call.tool == "run_tests":
                if tr.ok:
                    consecutive_no_improve = 0
                    next_prompt = build_next_step_prompt(tr)
                else:
                    consecutive_no_improve += 1
                    if consecutive_no_improve >= 2 and checkpoint:
                        self._rollback_checkpoint(tools, checkpoint, repair_case.allowed_files)
                        consecutive_no_improve = 0
                        checkpoint = self._save_checkpoint(tools, phase, step_idx, repair_case.allowed_files)
                        next_prompt = "已回滚到上一个 checkpoint。请重新分析问题并尝试不同策略。"
                    else:
                        diff_r = tools.git_diff()
                        diff = diff_r.output if diff_r.ok else None
                        violated_item = ""
                        if repair_spec:
                            violated_item = " | ".join(repair_spec.postconditions[:3] + repair_spec.invariants[:2])
                        next_prompt = build_spec_violation_feedback(
                            failed_command=context.target_test_command or "pytest -q",
                            failure_summary=tr.output or tr.error or "",
                            violated_spec_item=violated_item,
                            current_diff=diff,
                            changed_files=list(repair_case.allowed_files),
                            remaining_retries=2 - consecutive_no_improve,
                        )
            else:
                next_prompt = build_next_step_prompt(tr)

            messages.append({"role": "assistant", "content": str(tool_call.model_dump())})
            messages.append({"role": "user", "content": next_prompt})

            step_idx += 1
            phase_steps += 1

        after_result = run_validation_plan(tools, validation_plan, "after", repair_spec)
        diff_r = tools.git_diff()
        diff = diff_r.output if diff_r.ok else None

        if after_result.target_ok and after_result.full_ok:
            result = RepairAgentResult(
                ok=True,
                status="fixed",
                summary=f"Spec-guided 修复完成 (最终阶段: {phase.value})",
                diff=diff,
                tests_run=validation_plan.target_commands + [validation_plan.full_command],
                target_test_passed=True,
                full_test_passed=True,
            )
        elif after_result.target_ok:
            result = RepairAgentResult(
                ok=False,
                status="test_failed",
                summary=f"目标测试通过但全量测试失败 (阶段: {phase.value})",
                diff=diff,
                tests_run=validation_plan.target_commands + [validation_plan.full_command],
                target_test_passed=True,
                full_test_passed=False,
            )
        else:
            result = RepairAgentResult(
                ok=False,
                status="test_failed",
                summary=f"达到最大步骤数，测试仍失败 (阶段: {phase.value})",
                diff=diff,
                tests_run=validation_plan.target_commands,
                target_test_passed=False,
                full_test_passed=False,
            )

        _save(context.job_id, steps, result)
        return result

    @staticmethod
    def _advance_phase(current: AgentPhase) -> tuple[AgentPhase, int]:
        order = list(AgentPhase)
        idx = order.index(current)
        if idx + 1 < len(order):
            return order[idx + 1], 0
        return AgentPhase.FINALIZE, 0

    @staticmethod
    def _save_checkpoint(tools: MiniRepairTools, phase: AgentPhase, step_idx: int, allowed_files: list[str]) -> Checkpoint:
        snapshots: dict[str, str] = {}
        for f in allowed_files:
            r = tools.read_file(f)
            if r.ok:
                snapshots[f] = r.output
        diff_r = tools.git_diff()
        return Checkpoint(
            phase=phase,
            step_index=step_idx,
            file_snapshots=snapshots,
            diff=diff_r.output if diff_r.ok else None,
        )

    @staticmethod
    def _rollback_checkpoint(tools: MiniRepairTools, checkpoint: Checkpoint, allowed_files: list[str]) -> None:
        for f in allowed_files:
            if f in checkpoint.file_snapshots:
                tools.rewrite_file(f, checkpoint.file_snapshots[f])

    def _call_llm(self, messages: list[dict[str, str]]) -> ToolCall:
        resp = self.llm.chat_json_flexible(messages)
        if isinstance(resp, dict):
            tool = resp.get("tool", "finish")
            args = resp.get("args", {})
            if not isinstance(args, dict):
                args = {}
            return ToolCall(tool=tool, args=args)
        return ToolCall(tool="finish", args={"status": "needs_human", "summary": "LLM 返回格式异常"})

    @staticmethod
    def _dispatch_tool(tools: MiniRepairTools, call: ToolCall) -> ToolResult:
        dispatch = {
            "read_file": lambda: tools.read_file(**call.args),
            "get_file_excerpt": lambda: tools.get_file_excerpt(**call.args),
            "search_text": lambda: tools.search_text(**call.args),
            "run_tests": lambda: tools.run_tests(**call.args),
            "apply_replace": lambda: tools.apply_replace(**call.args),
            "rewrite_file": lambda: tools.rewrite_file(**call.args),
            "git_diff": lambda: tools.git_diff(),
            "finish": lambda: tools.finish(**call.args),
        }

        fn = dispatch.get(call.tool)
        if fn is None:
            return ToolResult(
                tool=call.tool, ok=False, output="",
                error=f"未知工具: {call.tool}",
            )
        try:
            return fn()
        except TypeError as e:
            return ToolResult(
                tool=call.tool, ok=False, output="",
                error=f"参数错误: {e}",
            )
        except Exception as e:
            return ToolResult(
                tool=call.tool, ok=False, output="",
                error=f"执行异常: {e}",
            )


def _save(job_id: str, steps: list[AgentStep], result: RepairAgentResult) -> None:
    try:
        save_repair_transcript(job_id, steps, result)
    except Exception as e:
        logger.warning("保存 transcript 失败: %s", e)