import os
import sys
import argparse
import json
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters.feishu import send_template_card, FEISHU_CARD_TEMPLATES
from autorepair.cards import (
    build_incident_detected_variables,
    build_repair_plan_ready_variables,
    build_fix_pr_ready_variables,
    build_manual_intervention_variables,
    build_periodic_digest_variables,
    CARD_KEY_MAPPING
)
from autorepair.config import config

def get_test_variables(card_type: str) -> dict:
    """获取测试用的卡片变量"""
    if card_type == "incident_detected":
        return build_incident_detected_variables(
            incident_id="INC-20260426-0001",
            service_name="Acme SupportDesk Lite",
            severity="P1",
            error_type="TypeError",
            error_message="SLA deadline comparison failed between timezone-aware and naive datetime",
            occurrence_count=6,
            time_window="10 分钟",
            issue_url="https://github.com/your-org/your-repo/issues/123",
            report_url="https://your-report-system.com/reports/INC-20260426-0001"
        )
    elif card_type == "repair_plan_ready":
        return build_repair_plan_ready_variables(
            incident_id="INC-20260426-0001",
            service_name="Acme SupportDesk Lite",
            root_cause="带时区时间与无时区时间直接比较导致TypeError，出现在sla_checker.py第42行",
            fix_strategy="统一转换为UTC aware datetime后再比较，修改比较逻辑增加类型校验",
            risk_level="低风险",
            policy_result="允许进入自动修复",
            report_url="https://your-report-system.com/reports/INC-20260426-0001"
        )
    elif card_type == "fix_pr_ready":
        return build_fix_pr_ready_variables(
            incident_id="INC-20260426-0001",
            service_name="Acme SupportDesk Lite",
            pr_number=123,
            pr_title="Fix timezone-aware SLA comparison error",
            fix_summary="统一SLA时间为UTC aware datetime，增加类型校验装饰器",
            test_brief="pytest 18/18 通过，新增3个边界用例",
            risk_level="低风险",
            pr_url="https://github.com/your-org/your-repo/pull/123",
            report_url="https://your-report-system.com/reports/INC-20260426-0001"
        )
    elif card_type == "manual_intervention":
        return build_manual_intervention_variables(
            incident_id="INC-20260426-0001",
            service_name="PaymentGateway",
            human_reason="疑似外部数据库连接异常，未定位到业务代码变更点，不适合自动修复",
            evidence_summary="健康检查连续5次失败，日志显示数据库连接超时，最近无代码部署",
            suggested_action="请检查数据库连接、网络配置与服务访问凭证",
            issue_url="https://github.com/your-org/your-repo/issues/123",
            report_url="https://your-report-system.com/reports/INC-20260426-0001"
        )
    elif card_type == "periodic_digest":
        return build_periodic_digest_variables(
            period_label="2026-04-26",
            summary_sentence="今日发现 8 个问题，自动修复 5 个，2 个需人工介入",
            metric_total=8,
            metric_fixed=5,
            metric_manual=2,
            success_rate="62.5%",
            avg_triage_time="4.2m",
            avg_repair_time="12.8m",
            top_errors_text="高频故障：SLA时间比较错误、数据库超时、缓存不可用",
            top_services_text="风险服务：SupportDesk、PaymentGateway、AuthService",
            todo_text="当前有 3 个 PR 待 Review，1 个 P0 需人工处理",
            report_url="https://your-report-system.com/daily/2026-04-26",
            pr_url="https://github.com/your-org/your-repo/pulls?q=is%3Apr+is%3Aopen+label%3Aautorepair"
        )
    else:
        raise ValueError(f"Unknown card type: {card_type}")


def send_test_feishu_card(card_type: str):
    """发送测试飞书卡片"""
    # 先输出模式
    mode = "real" if config.is_feishu_ready() else "mock"
    if mode == "mock":
        missing = []
        if not config.FEISHU_APP_ID:
            missing.append("FEISHU_APP_ID")
        if not config.FEISHU_APP_SECRET:
            missing.append("FEISHU_APP_SECRET")
        if not config.FEISHU_CHAT_ID:
            missing.append("FEISHU_CHAT_ID")
        print(f"Feishu mode: mock, reason: missing {', '.join(missing)}")
    else:
        print("Feishu mode: real")
    
    # 获取测试变量
    variables = get_test_variables(card_type)
    variable_count = len(variables)
    
    # 校验变量数不超过10
    allowed_keys = CARD_KEY_MAPPING[card_type]
    if variable_count > 10:
        print(f"ERROR: variable_count {variable_count} > 10, variables: {list(variables.keys())}")
        exit(1)
    
    # 校验变量key集合正确
    actual_keys = set(variables.keys())
    if actual_keys != allowed_keys:
        extra = actual_keys - allowed_keys
        missing = allowed_keys - actual_keys
        print(f"ERROR: key mismatch, extra: {extra}, missing: {missing}")
        exit(1)
    
    # 使用统一配置的模板ID
    template_id = FEISHU_CARD_TEMPLATES[card_type]
    
    # 输出信息
    print(f"\ntemplate_name: {card_type}")
    print(f"template_id: {template_id}")
    print(f"variable_count: {variable_count}")
    print(f"variables keys: {list(variables.keys())}")
    print(f"mode: {mode}")
    
    # 发送卡片
    result = send_template_card(card_type, variables)
    if result:
        if mode == "real":
            print(f"ok: true, message_id: {result.get('data', {}).get('message_id')}")
        else:
            print("ok: true")
    else:
        print(f"ok: false, error: 发送卡片失败")
        exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send test Feishu card")
    parser.add_argument(
        "--type", 
        required=True, 
        choices=["incident_detected", "repair_plan_ready", "fix_pr_ready", "manual_intervention", "periodic_digest"],
        help="Card type to send"
    )
    args = parser.parse_args()
    send_test_feishu_card(args.type)
