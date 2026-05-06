from __future__ import annotations

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.spec_builder import RepairSpec


class ZeroDivisionSkill:
    name = "ZeroDivisionSkill"

    def match(self, case: RepairCase, spec: RepairSpec) -> bool:
        text = f"{case.bug_type} {case.current_failure} {spec.violation}".lower()
        return any(kw in text for kw in [
            "zerodivision", "zero division", "division by zero",
        ])

    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str:
        return (
            "零除修复策略:\n"
            "1. 在除法前检查分母是否为零\n"
            "2. total_amount <= 0 时返回业务错误（如 400 Invalid order amount）\n"
            "3. 保持正常订单逻辑不变\n"
            "4. 对于 FastAPI 端点，使用 HTTPException(status_code=400) 返回"
        )

    def allowed_files_hint(self, case: RepairCase) -> list[str]:
        return case.allowed_files

    def success_criteria(self, spec: RepairSpec) -> list[str]:
        return spec.postconditions