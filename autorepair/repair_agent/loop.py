from __future__ import annotations

import logging
from pathlib import Path

from autorepair.adapters.llm_client import LLMClient
from autorepair.repair_agent.prompts import (
    build_initial_user_prompt,
    build_next_step_prompt,
    build_repair_agent_system_prompt,
)
from autorepair.repair_agent.schemas import (
    AgentStep,
    RepairAgentContext,
    RepairAgentResult,
    ToolCall,
    ToolResult,
)
from autorepair.repair_agent.tools import MiniRepairTools
from autorepair.repair_agent.transcript_store import save_repair_transcript

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

                changed = [str(p) for p in Path(context.worktree_path).rglob("*.py")
                           if str(p.relative_to(context.worktree_path)) in (diff or "")]

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

    def _call_llm(self, messages: list[dict[str, str]]) -> ToolCall:
        resp = self.llm.chat_json(messages)
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
