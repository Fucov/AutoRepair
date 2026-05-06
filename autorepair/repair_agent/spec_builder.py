from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from autorepair.repair_agent.repair_case import RepairCase
from autorepair.repair_agent.schemas import RepairAgentContext


class RepairSpec(BaseModel):
    spec_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_id: str
    case_id: str
    function_under_repair: str | None = None
    caller_expectation: str = ""
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    violation: str = ""
    acceptance_tests: list[str] = Field(default_factory=list)


def build_repair_spec(
    case: RepairCase,
    context: RepairAgentContext,
    code_excerpt: str | None = None,
    issue_body: str | None = None,
) -> RepairSpec:
    scenario_id = case.scenario_id
    template = _SPEC_TEMPLATES.get(scenario_id)

    if template:
        return RepairSpec(
            incident_id=case.incident_id,
            case_id=case.case_id,
            function_under_repair=template["function_under_repair"],
            caller_expectation=template["caller_expectation"],
            preconditions=template["preconditions"],
            postconditions=template["postconditions"],
            invariants=template["invariants"],
            violation=template["violation"],
            acceptance_tests=case.target_tests,
        )

    return RepairSpec(
        incident_id=case.incident_id,
        case_id=case.case_id,
        caller_expectation=f"修复 {case.bug_type}: {case.current_failure}",
        preconditions=[],
        postconditions=[],
        invariants=[],
        violation=case.current_failure,
        acceptance_tests=case.target_tests,
    )


_SPEC_TEMPLATES: dict[str, dict[str, Any]] = {
    "ticket-timezone-sla": {
        "function_under_repair": "submit_ticket",
        "caller_expectation": "submit_ticket 接受带时区的 sla_deadline，返回创建的工单",
        "preconditions": [
            "sla_deadline 是 ISO 8601 格式字符串",
            "sla_deadline 可能是带时区的，也可能是不带时区的"
        ],
        "postconditions": [
            "fromisoformat 结果必须为 timezone-aware datetime",
            "naive/aware 时间比较必须统一到 UTC aware",
            "过期工单返回 overdue 状态",
            "未过期工单返回 open 状态"
        ],
        "invariants": [
            "不得使用 datetime.utcnow() 与 aware datetime 比较",
            "所有 datetime 比较必须在同一时区基础上进行"
        ],
        "violation": "从 naive datetime 来源解析的 deadline 与 utcnow() 的 aware datetime 比较导致 TypeError: can't compare offset-naive and offset-aware datetimes"
    },
    "ticket-idempotency-duplicate": {
        "function_under_repair": "submit_ticket",
        "caller_expectation": "相同 idempotency_key 重复提交返回同一 ticket_id，不创建重复工单",
        "preconditions": [
            "idempotency_key 是字符串",
            "ticket_repository 中有 find_by_idempotency_key 方法"
        ],
        "postconditions": [
            "find_by_idempotency_key 查询到已有 ticket 时直接返回该 ticket",
            "新 idempotency_key 正常创建工单"
        ],
        "invariants": [
            "同一 idempotency_key 对应唯一 ticket_id",
            "重复提交不得增加数据库记录数"
        ],
        "violation": "submit_ticket 省略了 idempotency_key 检查逻辑，每次都创建新工单"
    },
    "ticket-nameerror-overdue": {
        "function_under_repair": "submit_ticket",
        "caller_expectation": "过期工单返回 overdue 状态，不应抛出 NameError",
        "preconditions": [
            "sla_deadline 是 ISO 8601 格式字符串"
        ],
        "postconditions": [
            "过期工单 status 为字符串 'overdue'",
            "不抛 NameError"
        ],
        "invariants": [
            "状态字段必须是字符串字面量，不能是未定义变量名"
        ],
        "violation": "代码中 status = overdue 缺少引号，overdue 作为变量名未定义导致 NameError"
    },
    "app-ticket-create-nameerror": {
        "function_under_repair": "create_ticket",
        "caller_expectation": "POST /ticket/create 在 sla_hours=8 时应正常创建工单并返回 success",
        "preconditions": [
            "priority 是请求中的优先级字符串",
            "sla_hours 可以是整数，sla_hours=8 是有效输入"
        ],
        "postconditions": [
            "sla_hours=8 时接口返回 HTTP 200",
            "响应 status 为 success",
            "不调用未定义函数，不抛 NameError"
        ],
        "invariants": [
            "不得为了消除异常而删除工单创建响应",
            "不得修改测试来绕过接口行为"
        ],
        "violation": "create_ticket 调用了未定义函数 calculate_priority(deadline)，导致 NameError"
    },
    "order-zero-division": {
        "function_under_repair": "calculate_order_discount",
        "caller_expectation": "calculate_order_discount 在 total_amount <= 0 时返回业务错误，而非抛异常",
        "preconditions": [
            "request.total_amount 是浮点数",
            "request.discount_amount 是浮点数"
        ],
        "postconditions": [
            "total_amount <= 0 时返回 400 Invalid order amount",
            "正常 total_amount > 0 时正常计算折扣"
        ],
        "invariants": [
            "除法前必须检查分母是否为零"
        ],
        "violation": "total_amount=0 直接做 discount_amount / total_amount 除法，抛 ZeroDivisionError"
    },
    "user-missing-profile": {
        "function_under_repair": "build_user_profile",
        "caller_expectation": "build_user_profile 在用户不存在时返回安全错误响应",
        "preconditions": [
            "user_id 是字符串"
        ],
        "postconditions": [
            "用户不存在时返回 None 或抛出 HTTPException(404)",
            "不抛 NoneType 错误"
        ],
        "invariants": [
            "访问字典属性前必须检查对象是否为 None"
        ],
        "violation": "get_user_by_id 返回 None 后直接访问 user['id']，抛 TypeError: 'NoneType' object is not subscriptable"
    }
}
