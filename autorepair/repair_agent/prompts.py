from __future__ import annotations

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
        "你是一个代码修复 Agent。\n"
        "你的任务是分析错误信息、阅读代码、定位 Bug 并修复它。\n\n"
        + TOOL_DESCRIPTIONS
    )


def build_initial_user_prompt(
    context: RepairAgentContext,
    test_output: str,
    code_excerpt: str | None = None,
) -> str:
    parts = [
        f"## 错误信息\n"
        f"- 错误类型: {context.error_type or '未知'}\n"
        f"- 错误消息: {context.error_message or '无'}\n"
        f"- 疑似文件: {context.suspected_file or '未知'}\n"
        f"- 疑似行号: {context.line_no or '未知'}",
    ]

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
