from datetime import datetime
from autorepair.agent.triage.evidence_collector import collect_incident_evidence
from autorepair.schemas import Incident, ErrorSummary

def test_evidence_collector_for_runtime_exception():
    incident = Incident(
        incident_id="test-123",
        source="local_log",
        service="order_service",
        error_summary=ErrorSummary(
            error_type="AttributeError",
            message="'NoneType' object has no attribute 'id'",
            suspected_file="order_service.py",
            line_no=45,
            function="process_order",
            fingerprint="test-fingerprint"
        ),
        raw_traceback="""
Traceback (most recent call last):
  File "order_service.py", line 45, in process_order
    order_id = order.id
AttributeError: 'NoneType' object has no attribute 'id'
        """,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )
    
    evidence = collect_incident_evidence(incident)
    assert len(evidence) >= 2
    assert any("Runtime Traceback" in e.label for e in evidence)
    assert any("order_service.py" in str(e.file) for e in evidence)
    assert any(e.line == 45 for e in evidence)
    assert any("Error Summary" in e.label for e in evidence)

def test_evidence_collector_for_github_issue():
    incident = Incident(
        incident_id="test-456",
        source="github_issue",
        service="order_service",
        error_summary=ErrorSummary(
            error_type="AssertionError",
            message="Expected 200, got 500",
            suspected_file="test_order_contract.py",
            line_no=12,
            function="test_order_contract",
            fingerprint="test-fingerprint-2"
        ),
        raw_traceback="Test failed with AssertionError",
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        issue_number=123,
        issue_url="https://github.com/test/repo/issues/123"
    )
    
    evidence = collect_incident_evidence(incident)
    assert len(evidence) >= 3
    assert any("GitHub Issue" in e.label for e in evidence)
    assert any("123" in e.detail for e in evidence)
