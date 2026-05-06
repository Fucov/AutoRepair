from __future__ import annotations

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.spec_builder import RepairSpec


class ImportScopeSkill:
    name = "ImportScopeSkill"

    def match(self, case: RepairCase, spec: RepairSpec) -> bool:
        text = f"{case.bug_type} {case.current_failure}".lower()
        return any(kw in text for kw in [
            "unboundlocalerror", "local variable", "import shadowing",
        ])

    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str:
        return (
            "导入作用域修复策略:\n"
            "1. 将局部 import 提升到模块或函数顶部\n"
            "2. 避免条件分支里局部变量遮蔽全局变量\n"
            "3. 检查是否有同名变量覆盖了导入的模块"
        )

    def allowed_files_hint(self, case: RepairCase) -> list[str]:
        return case.allowed_files

    def success_criteria(self, spec: RepairSpec) -> list[str]:
        return spec.postconditions