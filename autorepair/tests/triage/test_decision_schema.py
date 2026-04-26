import pytest
from pydantic import ValidationError
from autorepair.agent.triage.decision_schema import (
    Evidence, Decision, DecisionEnum, ConfidenceEnum, SeverityEnum, IncidentTypeEnum
)

def test_evidence_schema():
    # Test valid evidence
    evidence = Evidence(
        label="Traceback found",
        detail="AttributeError: 'NoneType' object has no attribute 'id'",
        file="order_service.py",
        line=45,
        command=None,
        sha="abc123"
    )
    assert evidence.label == "Traceback found"
    
    # Test minimal evidence
    minimal = Evidence(label="Test failure", detail="Test order_contract failed")
    assert minimal.file is None

def test_decision_schema():
    # Test valid auto_fix decision
    decision = Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="AttributeError in order service when processing empty order",
        root_cause_hypothesis="Missing null check for order_id parameter",
        evidence=[
            Evidence(
                label="Traceback",
                detail="AttributeError: 'NoneType' object has no attribute 'id'",
                file="order_service.py",
                line=45
            )
        ],
        risks=["No data loss risk, limited to order processing flow"],
        recommended_action="Apply null check to order_id parameter",
        fix_plan="Add if order_id is None: raise InvalidOrderError() at line 45",
        requires_human_approval=False,
        feishu_card={"title": "已完成诊断，准备自动修复"}
    )
    assert decision.decision == DecisionEnum.auto_fix
    assert decision.requires_human_approval is False
    
    # Test invalid decision (missing required field)
    with pytest.raises(ValidationError):
        Decision(
            decision="invalid",  # Invalid enum value
            confidence=ConfidenceEnum.high,
            severity=SeverityEnum.p1,
            incident_type=IncidentTypeEnum.runtime_exception,
            summary="Test",
            root_cause_hypothesis="Test",
            evidence=[],
            risks=[],
            recommended_action="Test",
            requires_human_approval=False,
            feishu_card={}
        )
