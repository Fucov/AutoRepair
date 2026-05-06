from __future__ import annotations

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.spec_builder import RepairSpec


class NullGuardSkill:
    name = "NullGuardSkill"

    def match(self, case: RepairCase, spec: RepairSpec) -> bool:
        text = f"{case.bug_type} {case.current_failure} {spec.violation}".lower()
        return any(kw in text for kw in [
            "nonetype", "object is not subscriptable", "user missing",
            "nonetype object", "none",
        ])

    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str:
        return (
            "空值防护策略:\n"
            "1. 在访问字典或对象属性前检查是否为 None\n"
            "2. 用户/资源不存在时返回明确的错误响应(404 或 None-safe)\n"
            "3. 不要吞掉异常返回错误成功\n"
            "4. 对于 FastAPI 端点，使用 HTTPException(status_code=404) 返回"
        )

    def allowed_files_hint(self, case: RepairCase) -> list[str]:
        return case.allowed_files

    def success_criteria(self, spec: RepairSpec) -> list[str]:
        return spec.postconditions