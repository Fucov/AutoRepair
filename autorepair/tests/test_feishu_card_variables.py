#!/usr/bin/env python3
"""
飞书卡片变量测试
验证每个卡片返回的key集合严格符合要求，且变量都是可JSON序列化的
"""
import json
import pytest

from autorepair.cards import (
    build_incident_detected_variables,
    build_repair_plan_ready_variables,
    build_fix_pr_ready_variables,
    build_manual_intervention_variables,
    build_periodic_digest_variables,
    INCIDENT_DETECTED_KEYS,
    REPAIR_PLAN_READY_KEYS,
    FIX_PR_READY_KEYS,
    MANUAL_INTERVENTION_KEYS,
    PERIODIC_DIGEST_KEYS
)


def test_incident_detected_variables_keys():
    """测试故障发现卡片变量key集合严格等于指定列表"""
    variables = build_incident_detected_variables(
        incident_id="INC-20260426-0001",
        service_name="TestService",
        severity="P1",
        error_type="TypeError",
        error_message="SLA deadline comparison failed",
        occurrence_count=6,
        time_window="10 分钟"
    )
    assert set(variables.keys()) == INCIDENT_DETECTED_KEYS
    assert len(variables) <= 10
    # 验证可JSON序列化
    json.dumps(variables)


def test_repair_plan_ready_variables_keys():
    """测试修复计划准备完成卡片变量key集合严格等于指定列表"""
    variables = build_repair_plan_ready_variables(
        incident_id="INC-20260426-0001",
        service_name="TestService",
        root_cause="带时区时间与无时区时间直接比较导致TypeError",
        fix_strategy="统一转换为UTC aware datetime后再比较",
        risk_level="低风险",
        policy_summary="允许进入自动修复"
    )
    assert set(variables.keys()) == REPAIR_PLAN_READY_KEYS
    assert len(variables) <= 10
    json.dumps(variables)


def test_fix_pr_ready_variables_keys():
    """测试PR准备完成卡片变量key集合严格等于指定列表"""
    variables = build_fix_pr_ready_variables(
        incident_id="INC-20260426-0001",
        service_name="TestService",
        pr_number=123,
        pr_title="Fix timezone-aware SLA comparison",
        fix_summary="统一SLA时间为UTC aware datetime",
        test_summary="pytest 18/18 通过",
        risk_level="低风险",
        pr_url="https://github.com/test/test/pull/123"
    )
    assert set(variables.keys()) == FIX_PR_READY_KEYS
    assert len(variables) <= 10
    json.dumps(variables)


def test_manual_intervention_variables_keys():
    """测试人工介入卡片变量key集合严格等于指定列表"""
    variables = build_manual_intervention_variables(
        incident_id="INC-20260426-0001",
        service_name="TestService",
        human_reason="疑似外部数据库连接异常，不适合自动改代码",
        evidence_summary="健康检查失败，日志未定位到业务代码变更点",
        next_action="请检查数据库连接、网络与服务凭证"
    )
    assert set(variables.keys()) == MANUAL_INTERVENTION_KEYS
    assert len(variables) <= 10
    json.dumps(variables)


def test_periodic_digest_variables_keys():
    """测试周期性总结卡片变量key集合严格等于指定列表"""
    variables = build_periodic_digest_variables(
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
        todo_text="当前有 3 个 PR 待 Review，1 个 P0 需人工处理"
    )
    assert set(variables.keys()) == PERIODIC_DIGEST_KEYS
    assert len(variables) <= 10
    json.dumps(variables)


def test_all_variables_are_serializable():
    """测试所有卡片变量值都是可JSON序列化的基本类型"""
    # 测试所有卡片构造函数返回的变量都可以序列化为JSON
    test_cases = [
        build_incident_detected_variables(
            "INC-001", "ServiceA", "P2", "ValueError", "Invalid input", 3
        ),
        build_repair_plan_ready_variables(
            "INC-001", "ServiceA", "Root cause", "Fix strategy", "中风险", "需人工确认"
        ),
        build_fix_pr_ready_variables(
            "INC-001", "ServiceA", 456, "Fix bug", "Fixed the issue", "Tests passed", "低风险", "https://pr.url"
        ),
        build_manual_intervention_variables(
            "INC-001", "ServiceA", "Cannot fix automatically", "No code changes found", "Manual check required"
        ),
        build_periodic_digest_variables(
            "2026-04-26", "Summary", 10, 7, 2, "70%", "3m", "10m", "Top errors", "Top services", "3 PRs to review"
        )
    ]
    
    for variables in test_cases:
        # 尝试序列化
        json_str = json.dumps(variables)
        # 反序列化后应该一致
        parsed = json.loads(json_str)
        assert parsed == variables


def test_text_truncation():
    """测试长文本会被正确截断"""
    long_error_message = "This is a very long error message that should be truncated to less than 80 characters. Let's make it even longer to test the truncation works correctly."
    
    variables = build_incident_detected_variables(
        incident_id="INC-001",
        service_name="TestService",
        severity="P3",
        error_type="RuntimeError",
        error_message=long_error_message,
        occurrence_count=1
    )
    
    assert len(variables["error_brief"]) <= 80
    assert variables["error_brief"].endswith("...")
