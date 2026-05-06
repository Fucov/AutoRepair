from __future__ import annotations

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.skills.base import RepairSkill
from autorepair.repair_agent.skills.datetime_timezone import DateTimeTimezoneSkill
from autorepair.repair_agent.skills.idempotency import IdempotencySkill
from autorepair.repair_agent.skills.import_scope import ImportScopeSkill
from autorepair.repair_agent.skills.name_error import NameErrorSkill
from autorepair.repair_agent.skills.null_guard import NullGuardSkill
from autorepair.repair_agent.skills.zero_division import ZeroDivisionSkill
from autorepair.repair_agent.spec_builder import RepairSpec

ALL_SKILLS: list[RepairSkill] = [
    DateTimeTimezoneSkill(),
    NullGuardSkill(),
    ZeroDivisionSkill(),
    IdempotencySkill(),
    NameErrorSkill(),
    ImportScopeSkill(),
]


def select_repair_skills(case: RepairCase, spec: RepairSpec) -> list[RepairSkill]:
    matched: list[RepairSkill] = []
    for skill in ALL_SKILLS:
        if skill.match(case, spec):
            matched.append(skill)
    return matched