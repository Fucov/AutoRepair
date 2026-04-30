from __future__ import annotations
import json
from autorepair.repair.context_collector import RepairContext
from autorepair.repair.patch_schema import PatchPlan


def build_patch_prompt(context: RepairContext) -> list[dict]:
    code_snippets_str = "\n\n".join([
        f"## {path}:\n```python\n{content}\n```"
        for path, content in context.code_snippets.items()
    ])
    
    existing_tests_str = "\n\n".join([
        f"## {path}:\n```python\n{content}\n```"
        for path, content in context.existing_tests.items()
    ])
    
    system_prompt = f"""你是谨慎的代码修复Agent，专门修复ticket-timezone-sla时区相关bug。

严格遵守以下规则：
1. 只修复与时区比较相关的TypeError问题，不要修改任何无关代码
2. 不要修改测试文件，不要放宽测试条件，不要删除现有测试
3. 输出必须是严格的JSON格式，完全匹配PatchPlan schema定义
4. 只能使用replace操作，old必须是原文件中存在的连续完整文本
5. 修复策略优先级：
   - 使用datetime.now(timezone.utc)获取当前时间
   - 将fromisoformat得到的deadline统一转成timezone-aware UTC时间
   - naive datetime默认补timezone.utc
   - aware datetime用astimezone(timezone.utc)转换
6. 必须包含测试命令，优先运行目标测试再运行全量测试
7. 不要读取或修改任何密钥、配置文件

PatchPlan schema定义：
{json.dumps(PatchPlan.model_json_schema(), indent=2, ensure_ascii=False)}

输出示例：
{{
  "summary": "Normalize SLA deadline and current time to timezone-aware UTC before comparison.",
  "files": [
    {{
      "path": "demo_service/ticket_service.py",
      "operation": "replace",
      "old": "def calculate_sla_deadline(deadline_str: str) -> datetime: ...",
      "new": "def calculate_sla_deadline(deadline_str: str) -> datetime: ..."
    }}
  ],
  "tests_to_run": [
    "pytest -q demo_service/tests/test_ticket_contract.py::test_timezone_aware_sla_deadline_should_create_ticket -m agent_target",
    "pytest -q"
  ],
  "risk_level": "low",
  "confidence": 0.88
}}
"""

    user_prompt = f"""请修复以下bug：

Incident ID: {context.incident_id}
Issue Number: #{context.issue_number}
错误类型: {context.error_type}
错误信息: {context.error_message}
疑似文件: {context.suspected_file}
行号: {context.line_no}

错误栈:
```
{context.raw_traceback}
```

相关代码:
{code_snippets_str}

相关测试:
{existing_tests_str}

目标测试命令: {context.target_test_command}
全量测试命令: {context.full_test_command}

请输出修复方案JSON。
"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
