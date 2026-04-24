from datetime import datetime
from autorepair.schemas import Incident, ErrorSummary
from autorepair.adapters.feishu import build_incident_card_payload


SAMPLE_ERROR_SUMMARY = ErrorSummary(
    error_type="TypeError",
    message="'NoneType' object is not subscriptable",
    suspected_file="demo_service/service.py",
    line_no=11,
    function="build_user_profile",
    fingerprint="8a3f2d7c9e1b"
)

SAMPLE_INCIDENT = Incident(
    incident_id="INC-20240501-120000-8a3f2d",
    source="local_log",
    service="demo_service",
    status="NEW",
    error_summary=SAMPLE_ERROR_SUMMARY,
    raw_traceback="Traceback ...",
    created_at=datetime.now().isoformat(),
    updated_at=datetime.now().isoformat(),
    scenario_id="user-missing-profile"
)

SAMPLE_GITHUB_INCIDENT = Incident(
    incident_id="INC-20240501-123000-7c9e1b",
    source="github_issue",
    service="demo_service",
    status="NEW",
    error_summary=SAMPLE_ERROR_SUMMARY,
    raw_traceback="Traceback ...",
    created_at=datetime.now().isoformat(),
    updated_at=datetime.now().isoformat(),
    issue_url="https://github.com/owner/repo/issues/123"
)


def test_feishu_card_contains_source():
    """测试飞书卡片包含来源信息"""
    payload = build_incident_card_payload(SAMPLE_INCIDENT)
    fields = payload["card"]["elements"][0]["fields"]
    field_contents = [f["text"]["content"] for f in fields]
    assert any("来源" in content for content in field_contents)
    assert any("local_log" in content for content in field_contents)


def test_feishu_card_contains_scenario_id():
    """测试飞书卡片包含场景ID"""
    payload = build_incident_card_payload(SAMPLE_INCIDENT)
    fields = payload["card"]["elements"][0]["fields"]
    field_contents = [f["text"]["content"] for f in fields]
    assert any("场景" in content for content in field_contents)
    assert any("user-missing-profile" in content for content in field_contents)


def test_feishu_card_contains_issue_url():
    """测试飞书卡片包含GitHub Issue链接"""
    payload = build_incident_card_payload(SAMPLE_GITHUB_INCIDENT)
    fields = payload["card"]["elements"][0]["fields"]
    field_contents = [f["text"]["content"] for f in fields]
    assert any("Issue链接" in content for content in field_contents)
    assert any("https://github.com/owner/repo/issues/123" in content for content in field_contents)


def test_feishu_card_contains_stage_note():
    """测试飞书卡片包含当前阶段说明"""
    payload = build_incident_card_payload(SAMPLE_INCIDENT)
    elements = payload["card"]["elements"]
    element_contents = [e["text"]["content"] for e in elements if "text" in e]
    assert any("等待 Agent 分析与自动修复" in content for content in element_contents)
