from pydantic import BaseModel
from typing import Literal, List


class BugScenario(BaseModel):
    scenario_id: str
    title: str
    trigger_type: Literal["local_log", "github_issue"]
    endpoint: str
    expected_error_type: str
    expected_behavior: str
    target_test_command: str


BUG_SCENARIOS: List[BugScenario] = [
    BugScenario(
        scenario_id="user-missing-profile",
        title="用户画像查询缺失异常",
        trigger_type="local_log",
        endpoint="GET /users/not-exist/profile",
        expected_error_type="TypeError",
        expected_behavior="返回404 User not found",
        target_test_command="pytest -q demo_service/tests/test_profile_contract.py::test_missing_user_should_return_404 -m agent_target"
    ),
    BugScenario(
        scenario_id="order-zero-division",
        title="订单金额为0时折扣计算异常",
        trigger_type="local_log",
        endpoint="POST /orders/preview",
        expected_error_type="ZeroDivisionError",
        expected_behavior="返回400 Invalid order amount",
        target_test_command="pytest -q demo_service/tests/test_order_contract.py::test_zero_total_amount_should_return_400 -m agent_target"
    ),
    BugScenario(
        scenario_id="ticket-timezone-sla",
        title="带时区 SLA 截止时间导致工单创建失败",
        trigger_type="local_log",
        endpoint="POST /tickets/submit",
        expected_error_type="TypeError",
        expected_behavior="成功创建工单，返回200",
        target_test_command="pytest -q demo_service/tests/test_ticket_contract.py::test_timezone_aware_sla_deadline_should_create_ticket -m agent_target"
    ),
    BugScenario(
        scenario_id="ticket-idempotency-duplicate",
        title="重复事件导致重复创建工单",
        trigger_type="github_issue",
        endpoint="POST /tickets/submit",
        expected_error_type="BusinessLogicError",
        expected_behavior="同一个幂等键返回同一个工单，不重复创建",
        target_test_command="pytest -q demo_service/tests/test_ticket_contract.py::test_duplicate_idempotency_key_should_not_create_two_tickets -m agent_target"
    )
]


def get_scenario_by_id(scenario_id: str) -> BugScenario | None:
    """根据scenario_id获取Bug场景配置"""
    for scenario in BUG_SCENARIOS:
        if scenario.scenario_id == scenario_id:
            return scenario
    return None
