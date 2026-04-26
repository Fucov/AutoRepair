import os
import json
from pathlib import Path
from autorepair.agent.triage.report_writer import write_triage_report
from autorepair.agent.triage.decision_schema import (
    Decision, DecisionEnum, ConfidenceEnum, SeverityEnum, IncidentTypeEnum, Evidence
)

def test_report_writer_generates_files(tmp_path):
    incident_id = "test-incident-123"
    decision = Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="AttributeError in order service",
        root_cause_hypothesis="Missing null check for order_id",
        evidence=[
            Evidence(
                label="Traceback",
                detail="AttributeError: 'NoneType' object has no attribute 'id'",
                file="order_service.py",
                line=45,
                sha="abc123"
            )
        ],
        risks=["Low risk, no data loss"],
        recommended_action="Apply null check",
        fix_plan="Add if order_id is None: raise InvalidOrderError()",
        requires_human_approval=False,
        feishu_card={"title": "已完成诊断，准备自动修复"}
    )
    
    # Override report directory for testing
    from autorepair.agent.triage import report_writer
    original_dir = report_writer.REPORT_DIR
    report_writer.REPORT_DIR = tmp_path
    
    try:
        report_path, decision_path = write_triage_report(
            incident_id=incident_id,
            incident_source="github_issue",
            git_sha="abc123",
            decision=decision,
            policy_passed=True,
            feishu_message_id="msg_123"
        )
        
        # Check files exist
        assert os.path.exists(report_path)
        assert os.path.exists(decision_path)
        
        # Check JSON content
        with open(decision_path, "r", encoding="utf-8") as f:
            saved_decision = json.load(f)
            assert saved_decision["decision"] == "auto_fix"
            assert saved_decision["confidence"] == "high"
        
        # Check Markdown content
        with open(report_path, "r", encoding="utf-8") as f:
            md_content = f.read()
            assert "test-incident-123" in md_content
            assert "AttributeError in order service" in md_content
            assert "order_service.py:45" in md_content
            assert "Policy gate result: ✅ PASSED" in md_content
            assert "msg_123" in md_content
        
        # Test update existing report
        decision.summary = "Updated summary"
        report_path2, decision_path2 = write_triage_report(
            incident_id=incident_id,
            incident_source="github_issue",
            git_sha="abc123",
            decision=decision,
            policy_passed=True
        )
        
        assert report_path2 == report_path
        assert decision_path2 == decision_path
        
        with open(report_path2, "r", encoding="utf-8") as f:
            assert "Updated summary" in f.read()
            
    finally:
        report_writer.REPORT_DIR = original_dir
