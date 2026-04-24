import tempfile
from pathlib import Path
from datetime import datetime
from autorepair.schemas import Incident, ErrorSummary
from autorepair.incident_store import append_incident, load_incidents, has_fingerprint

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


def test_append_and_load_incidents():
    """测试追加和加载Incident"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        # 追加Incident
        append_incident(SAMPLE_INCIDENT, temp_path)
        # 加载Incident
        incidents = load_incidents(temp_path)
        assert len(incidents) == 1
        assert incidents[0].incident_id == SAMPLE_INCIDENT.incident_id
        assert incidents[0].error_summary.fingerprint == SAMPLE_ERROR_SUMMARY.fingerprint
    finally:
        temp_path.unlink()


def test_has_fingerprint():
    """测试指纹去重功能"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        # 追加Incident
        append_incident(SAMPLE_INCIDENT, temp_path)
        # 检查指纹存在
        assert has_fingerprint(SAMPLE_ERROR_SUMMARY.fingerprint, temp_path) is True
        # 检查不存在的指纹
        assert has_fingerprint("not_exist_fingerprint", temp_path) is False
    finally:
        temp_path.unlink()


def test_load_empty_file():
    """测试加载不存在的文件返回空列表"""
    incidents = load_incidents("/non/existent/path/incidents.jsonl")
    assert incidents == []
