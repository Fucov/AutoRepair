from __future__ import annotations

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.spec_builder import RepairSpec


class DateTimeTimezoneSkill:
    name = "DateTimeTimezoneSkill"

    def match(self, case: RepairCase, spec: RepairSpec) -> bool:
        text = f"{case.bug_type} {case.current_failure} {spec.violation}".lower()
        return any(kw in text for kw in [
            "offset-naive", "offset-aware", "timezone", "datetime.utcnow",
            "can't compare", "utcnow", "naive", "aware",
        ])

    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str:
        return (
            "时区修复策略:\n"
            "1. 将 datetime.utcnow() 替换为 datetime.now(timezone.utc)\n"
            "2. fromisoformat 解析后检查 tzinfo:\n"
            "   - naive datetime: .replace(tzinfo=timezone.utc)\n"
            "   - aware datetime: .astimezone(timezone.utc)\n"
            "3. 确保导入 from datetime import datetime, timezone\n"
            "4. 不要用 datetime.utcnow() 与 aware datetime 比较\n"
            "5. 统一将所有 datetime 转换为 UTC aware 后再比较"
        )

    def allowed_files_hint(self, case: RepairCase) -> list[str]:
        return case.allowed_files

    def success_criteria(self, spec: RepairSpec) -> list[str]:
        return spec.postconditions