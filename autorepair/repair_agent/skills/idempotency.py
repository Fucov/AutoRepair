from __future__ import annotations

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.spec_builder import RepairSpec


class IdempotencySkill:
    name = "IdempotencySkill"

    def match(self, case: RepairCase, spec: RepairSpec) -> bool:
        text = f"{case.bug_type} {case.current_failure} {spec.violation}".lower()
        return any(kw in text for kw in [
            "idempotency", "duplicate", "same ticket_id", "idempotent",
        ])

    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str:
        return (
            "幂等性修复策略:\n"
            "1. 在创建工单前，先用 find_by_idempotency_key 查询已有 ticket\n"
            "2. 如果已存在，直接返回已有 ticket\n"
            "3. 不要创建重复工单\n"
            "4. 正常新 key 仍应创建新工单\n"
            "5. 使用 ticket_repository.find_by_idempotency_key 进行查询"
        )

    def allowed_files_hint(self, case: RepairCase) -> list[str]:
        return case.allowed_files

    def success_criteria(self, spec: RepairSpec) -> list[str]:
        return spec.postconditions