from __future__ import annotations

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.spec_builder import RepairSpec


class NameErrorSkill:
    name = "NameErrorSkill"

    def match(self, case: RepairCase, spec: RepairSpec) -> bool:
        text = f"{case.bug_type} {case.current_failure}".lower()
        return "nameerror" in text and "nonetype" not in text

    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str:
        return (
            "NameError 修复策略:\n"
            "1. 判断未定义符号是否应是字符串字面量\n"
            "2. 如果变量名看起来像状态/字符串值，添加引号\n"
            "3. 如果是调用了未定义的函数（如 calculate_priority），"
            "直接用简单表达式替换该调用，或删除该行\n"
            "4. 不要引入无关变量\n"
            "5. 检查是否缺少导入语句"
        )

    def allowed_files_hint(self, case: RepairCase) -> list[str]:
        return case.allowed_files

    def success_criteria(self, spec: RepairSpec) -> list[str]:
        return spec.postconditions