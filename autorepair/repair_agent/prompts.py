from __future__ import annotations

from typing import Any

from autorepair.repair_agent.schemas import RepairAgentContext, ToolResult

TOOL_DESCRIPTIONS = """你拥有以下 8 个工具：

1. read_file(path, line_range?) — 读取文件内容。line_range 格式 "10-20"。
2. get_file_excerpt(path, line, context=30) — 读取某行附近的上下文。
3. search_text(query, file_glob?, max_results=30) — 在代码库中搜索文本。
4. run_tests(command, timeout=120) — 运行 pytest 测试。命令必须以 pytest 开头。
5. apply_replace(path, old, new) — 在文件中精确替换一段文本。old 必须唯一匹配。
6. rewrite_file(path, content) — 整体重写文件内容（需先 read_file）。
7. git_diff() — 查看当前 git diff。
8. finish(status, summary) — 结束修复。status 可选: fixed, test_failed, not_reproducible, needs_human, unsafe_patch。

规则：
- 每次回复只调用一个工具。
- 调用格式为 JSON: {"tool": "工具名", "args": {参数字典}}
- 读代码 → 分析 → 小步替换 → 测试，循环修复。
- 需要 human 才能判断的情况调用 finish(needs_human)。
- 修复完成后运行目标测试和全量测试，确认通过后调用 finish(fixed)。
"""


def build_repair_agent_system_prompt() -> str:
    return (
        "你是安全的代码修复 Agent。\n"
        "你的目标不是让报错消失，而是满足 RepairSpec 中的规格要求。\n\n"
        "核心规则：\n"
        "1. 只能修改 allowed_files 中列出的文件\n"
        "2. 默认禁止修改测试文件\n"
        "3. 不要删除功能，不要绕过测试\n"
        "4. 优先最小修改\n"
        "5. 每次修改必须说明满足哪条 postcondition / invariant\n"
        "6. 如果无法满足规格，调用 finish(needs_human)\n"
        "7. 输出必须是 JSON ToolCall，不要 markdown\n\n"
        + TOOL_DESCRIPTIONS
    )


def build_initial_user_prompt(
    context: RepairAgentContext,
    test_output: str,
    code_excerpt: str | None = None,
    repair_case: Any | None = None,
    repair_spec: Any | None = None,
    skills: list[Any] | None = None,
    validation_plan: Any | None = None,
    history_context: Any | None = None,
) -> str:
    parts = [
        f"## 错误信息\n"
        f"- 错误类型: {context.error_type or '未知'}\n"
        f"- 错误消息: {context.error_message or '无'}\n"
        f"- 疑似文件: {context.suspected_file or '未知'}\n"
        f"- 疑似行号: {context.line_no or '未知'}",
    ]

    if repair_case:
        parts.append(
            f"## RepairCase\n"
            f"- case_id: {repair_case.case_id}\n"
            f"- scenario_id: {repair_case.scenario_id or '未知'}\n"
            f"- bug_type: {repair_case.bug_type}\n"
            f"- entrypoint: {repair_case.entrypoint or '未知'}\n"
            f"- expected_behavior: {repair_case.expected_behavior}\n"
            f"- confidence: {repair_case.confidence}"
        )
        parts.append(
            f"## 文件约束\n"
            f"- allowed_files: {repair_case.allowed_files}\n"
            f"- forbidden_files: {repair_case.forbidden_files}\n"
            f"- target_tests: {repair_case.target_tests}"
        )

    if repair_spec:
        parts.append(
            f"## RepairSpec\n"
            f"- function_under_repair: {repair_spec.function_under_repair or '未知'}\n"
            f"- caller_expectation: {repair_spec.caller_expectation}\n"
            f"- preconditions: {repair_spec.preconditions}\n"
            f"- postconditions: {repair_spec.postconditions}\n"
            f"- invariants: {repair_spec.invariants}\n"
            f"- violation: {repair_spec.violation}"
        )

    if skills:
        skill_info = []
        for skill in skills:
            skill_info.append(f"- {skill.name}: {skill.prompt_hint(repair_case, repair_spec)}")
        parts.append("## 选中的 RepairSkill\n" + "\n".join(skill_info))

    if validation_plan:
        parts.append(
            f"## ValidationPlan\n"
            f"- target_commands: {validation_plan.target_commands}\n"
            f"- full_command: {validation_plan.full_command}"
        )

    if history_context and history_context.recent_commits:
        parts.append(
            f"## Git History\n"
            f"- file: {history_context.file}\n"
            f"- recent_commits: {history_context.recent_commits[:5]}\n"
            f"- last_modifier: {history_context.last_modifier_summary}"
        )

    if context.raw_traceback:
        parts.append(f"## 原始 Traceback\n```\n{context.raw_traceback}\n```")

    if code_excerpt:
        parts.append(f"## 可疑文件上下文\n```\n{code_excerpt}\n```")

    if test_output:
        parts.append(f"## 目标测试输出\n```\n{test_output}\n```")

    if context.target_test_command:
        parts.append(f"## 目标测试命令\n`{context.target_test_command}`")

    parts.append(f"## 全量测试命令\n`{context.full_test_command}`")
    parts.append("请开始分析和修复。")

    return "\n\n".join(parts)


def build_next_step_prompt(last_result: ToolResult, current_diff: str | None = None) -> str:
    parts = []

    if last_result.tool == "run_tests":
        if last_result.ok:
            parts.append(f"目标测试已通过。输出:\n```\n{last_result.output[-1000:]}\n```")
            if current_diff:
                parts.append(f"当前 diff:\n```diff\n{current_diff}\n```")
            parts.append("请运行全量测试确认无回归，然后调用 finish(fixed)。")
        else:
            parts.append(f"测试失败:\n```\n{last_result.output[-1500:] if last_result.output else last_result.error}\n```")
            parts.append("请分析失败原因并继续修复。")
    elif last_result.tool == "apply_replace":
        if last_result.ok:
            parts.append("替换成功。")
            if current_diff:
                parts.append(f"当前 diff:\n```diff\n{current_diff}\n```")
            parts.append("请运行目标测试验证修复。")
        else:
            parts.append(f"替换失败: {last_result.error}")
            parts.append("请重新 read_file 确认文件内容后重试。")
    else:
        if last_result.ok:
            parts.append(f"{last_result.tool} 执行成功:\n```\n{last_result.output[:1500]}\n```")
        else:
            parts.append(f"{last_result.tool} 执行失败: {last_result.error}")
        parts.append("请继续。")

    return "\n\n".join(parts)


def build_spec_violation_feedback(
    failed_command: str,
    failure_summary: str,
    violated_spec_item: str,
    current_diff: str | None,
    changed_files: list[str],
    remaining_retries: int,
) -> str:
    parts = [
        "## 测试失败 - 规格违反反馈",
        f"### 失败命令\n`{failed_command}`",
        f"### 失败输出\n```\n{failure_summary[:1500]}\n```",
    ]

    if violated_spec_item:
        parts.append(f"### 违反的规格\n{violated_spec_item}")

    if current_diff:
        parts.append(f"### 当前 diff\n```diff\n{current_diff[:3000]}\n```")

    if changed_files:
        parts.append(f"### 已修改文件\n{changed_files}")

    parts.append(f"### 剩余重试次数\n{remaining_retries}")
    parts.append(
        "请仔细分析违反了 RepairSpec 的哪条 postcondition/invariant，"
        "调整修复策略。如果无法修复，请调用 finish(needs_human)。"
    )

    return "\n\n".join(parts)
