import tempfile
from datetime import datetime
from autorepair.schemas import Incident, ErrorSummary
from autorepair.incident_store import upsert_incident_by_fingerprint, load_incidents


SAMPLE_ERROR_SUMMARY = ErrorSummary(
    error_type="TypeError",
    message="'NoneType' object is not subscriptable",
    suspected_file="demo_service/service.py",
    line_no=11,
    function="build_user_profile",
    fingerprint="8a3f2d7c9e1b"
)

SAMPLE_ERROR_SUMMARY_2 = ErrorSummary(
    error_type="ZeroDivisionError",
    message="division by zero",
    suspected_file="demo_service/order_service.py",
    line_no=16,
    function="calculate_order_discount",
    fingerprint="7c9e1b8a3f2d"
)


def test_upsert_incident_created():
    """测试第一次插入时action为created"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        incident = Incident(
            incident_id="INC-20240501-120000-8a3f2d",
            source="local_log",
            service="demo_service",
            status="NEW",
            error_summary=SAMPLE_ERROR_SUMMARY,
            raw_traceback="Traceback ...",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        final_incident, action = upsert_incident_by_fingerprint(incident, temp_path)
        assert action == "created"
        assert final_incident.occurrence_count == 1
        assert final_incident.first_seen_at is not None
        assert final_incident.last_seen_at is not None
        
        incidents = load_incidents(temp_path)
        assert len(incidents) == 1
    finally:
        temp_path.unlink()


def test_upsert_incident_updated():
    """测试相同指纹第二次插入时action为updated，occurrence_count增加"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        # 第一次插入
        incident1 = Incident(
            incident_id="INC-20240501-120000-8a3f2d",
            source="local_log",
            service="demo_service",
            status="NEW",
            error_summary=SAMPLE_ERROR_SUMMARY,
            raw_traceback="Traceback ...",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        inc1, action1 = upsert_incident_by_fingerprint(incident1, temp_path)
        assert action1 == "created"
        assert inc1.occurrence_count == 1
        
        # 第二次插入相同指纹
        incident2 = Incident(
            incident_id="INC-20240501-120100-8a3f2d",
            source="local_log",
            service="demo_service",
            status="NEW",
            error_summary=SAMPLE_ERROR_SUMMARY,
            raw_traceback="Traceback ...",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        inc2, action2 = upsert_incident_by_fingerprint(incident2, temp_path)
        assert action2 == "updated"
        assert inc2.occurrence_count == 2
        assert inc2.last_seen_at > inc2.first_seen_at
        
        # 检查文件中只有一条记录
        incidents = load_incidents(temp_path)
        assert len(incidents) == 1
        assert incidents[0].occurrence_count == 2
    finally:
        temp_path.unlink()


def test_upsert_incident_source_refs_append():
    """测试不同source_ref会被追加到列表且去重"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)
    
    try:
        # 第一次插入带source_ref
        incident1 = Incident(
            incident_id="INC-20240501-120000-8a3f2d",
            source="local_log",
            service="demo_service",
            status="NEW",
            error_summary=SAMPLE_ERROR_SUMMARY,
            raw_traceback="Traceback ...",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source_ref="log/path:123"
        )
        inc1, _ = upsert_incident_by_fingerprint(incident1, temp_path)
        assert "log/path:123" in inc1.source_refs
        assert len(inc1.source_refs) == 1
        
        # 第二次插入相同指纹不同source_ref
        incident2 = Incident(
            incident_id="INC-20240501-120100-8a3f2d",
            source="local_log",
            service="demo_service",
            status="NEW",
            error_summary=SAMPLE_ERROR_SUMMARY,
            raw_traceback="Traceback ...",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source_ref="log/path:456"
        )
        inc2, _ = upsert_incident_by_fingerprint(incident2, temp_path)
        assert "log/path:123" in inc2.source_refs
        assert "log/path:456" in inc2.source_refs
        assert len(inc2.source_refs) == 2
        
        # 第三次插入相同source_ref，不重复
        incident3 = Incident(
            incident_id="INC-20240501-120200-8a3f2d",
            source="local_log",
            service="demo_service",
            status="NEW",
            error_summary=SAMPLE_ERROR_SUMMARY,
            raw_traceback="Traceback ...",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source_ref="log/path:123"
        )
        inc3, _ = upsert_incident_by_fingerprint(incident3, temp_path)
        assert len(inc3.source_refs) == 2
    finally:
        temp_path.unlink()
