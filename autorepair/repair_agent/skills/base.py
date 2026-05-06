from __future__ import annotations

from typing import Protocol, runtime_checkable

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.spec_builder import RepairSpec


@runtime_checkable
class RepairSkill(Protocol):
    name: str

    def match(self, case: RepairCase, spec: RepairSpec) -> bool: ...

    def prompt_hint(self, case: RepairCase, spec: RepairSpec) -> str: ...

    def allowed_files_hint(self, case: RepairCase) -> list[str]: ...

    def success_criteria(self, spec: RepairSpec) -> list[str]: ...