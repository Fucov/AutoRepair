from __future__ import annotations

import json

from autorepair.repair.context_collector import RepairContext
from autorepair.repair.patch_schema import PatchPlan

_SYSTEM_PROMPT = """你是专业的代码修复Agent，能分析任何 Python 运行时错误并生成最小化修复补丁。

严格遵守以下规则：
1. 分析错误栈，定位根因，阅读相关代码，理解上下文。
2. 只修改必须修改的代码，保持最小化改动。
3. 不修改测试文件，除非测试本身存在 bug。
4. 不修改配置文件，不读取或输出密钥。
5. old 必须是文件中实际存在的连续完整文本（包括缩进），不能凭空编造。
6. 如果确实无法修复，在 summary 中说明具体原因和建议的解决方法，files 留空列表。
7. tests_to_run 中必须包含至少一个 pytest 命令。
8. 修复后不能引入新的语法错误或类型错误。
9. 优先修复源码文件，不要尝试修复第三方库。

PatchPlan schema 定义：
{schema}

输出要求：严格输出合法 JSON，不要包含 markdown 代码块标记。
"""

_USER_TEMPLATE = """请修复以下 bug：

Incident ID: {incident_id}
Issue Number: #{issue_number}
错误类型: {error_type}
错误信息: {error_message}
疑似文件: {suspected_file}
行号: {line_no}

错误栈:
```
{raw_traceback}
```

相关代码:
{code_snippets}

相关测试:
{existing_tests}

项目结构:
```
{project_structure}
```

依赖信息:
```
{dependencies}
```

目标测试命令: {target_test_command}
全量测试命令: {full_test_command}

请输出修复方案 JSON。
"""

_RETRY_TEMPLATE = """修复失败，需要重新生成方案。

上次失败原因：
{failure_detail}

上次生成的方案：
```json
{last_plan_json}
```

请根据失败信息修正你的修复方案，特别注意：
- 如果是 old 内容不匹配，请确保从代码中精确复制文本，包括所有缩进和换行。
- 如果是测试失败，请分析测试输出，理解期望行为，调整修复策略。
- 如果是回归测试失败，说明修复引入了新问题，请缩小修改范围。

请输出修正后的修复方案 JSON。
"""


def build_patch_prompt(context: RepairContext) -> list[dict]:
    code_snippets_str = "\n\n".join(
        f"## {path}:\n```python\n{content}\n```"
        for path, content in context.code_snippets.items()
    ) or "(无代码片段)"

    existing_tests_str = "\n\n".join(
        f"## {path}:\n```python\n{content}\n```"
        for path, content in context.existing_tests.items()
    ) or "(无相关测试)"

    system_prompt = _SYSTEM_PROMPT.format(
        schema=json.dumps(PatchPlan.model_json_schema(), indent=2, ensure_ascii=False),
    )

    user_prompt = _USER_TEMPLATE.format(
        incident_id=context.incident_id,
        issue_number=context.issue_number,
        error_type=context.error_type,
        error_message=context.error_message,
        suspected_file=context.suspected_file or "unknown",
        line_no=context.line_no or "unknown",
        raw_traceback=context.raw_traceback,
        code_snippets=code_snippets_str,
        existing_tests=existing_tests_str,
        project_structure=context.project_structure or "(未知)",
        dependencies=context.dependencies or "(未知)",
        target_test_command=context.target_test_command,
        full_test_command=context.full_test_command,
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_retry_prompt(
    existing_messages: list[dict],
    last_plan_json: str,
    failure_detail: str,
) -> list[dict]:
    retry_msg = _RETRY_TEMPLATE.format(
        failure_detail=failure_detail,
        last_plan_json=last_plan_json,
    )
    return existing_messages + [
        {"role": "assistant", "content": last_plan_json},
        {"role": "user", "content": retry_msg},
    ]
