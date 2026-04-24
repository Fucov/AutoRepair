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
    updated_at=datetime.now().isoformat()
)


def test_build_incident_card_payload():
    """测试构造飞书卡片Payload包含必要字段"""
    payload = build_incident_card_payload(SAMPLE_INCIDENT)
    
    # 检查卡片基本结构
    assert payload["msg_type"] == "interactive"
    assert "card" in payload
    assert "header" in payload["card"]
    assert "elements" in payload["card"]
    
    # 检查标题包含incident_id
    header_title = payload["card"]["header"]["title"]["content"]
    assert SAMPLE_INCIDENT.incident_id in header_title
    
    # 检查字段包含必要信息
    fields = payload["card"]["elements"][0]["fields"]
    field_contents = [f["text"]["content"] for f in fields]
    
    assert any("demo_service" in content for content in field_contents)
    assert any("TypeError" in content for content in field_contents)
    assert any("demo_service/service.py:11" in content for content in field_contents)
    assert any("NEW" in content for content in field_contents)
    assert any(SAMPLE_ERROR_SUMMARY.fingerprint in content for content in field_contents)
