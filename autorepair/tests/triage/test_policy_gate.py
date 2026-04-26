from autorepair.agent.triage.policy_gate import should_auto_fix
from autorepair.agent.triage.decision_schema import (
    Decision, DecisionEnum, ConfidenceEnum, SeverityEnum, IncidentTypeEnum, Evidence
)

def test_valid_auto_fix_passes():
    decision = Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="Test",
        root_cause_hypothesis="Test",
        evidence=[Evidence(label="Traceback", detail="Error found")],
        risks=["Low risk"],
        recommended_action="Fix",
        fix_plan="Add null check",
        requires_human_approval=False,
        feishu_card={}
    )
    allowed, reason = should_auto_fix(decision)
    assert allowed is True
    assert reason == ""

def test_low_confidence_auto_fix_blocked():
    decision = Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.low,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="Test",
        root_cause_hypothesis="Test",
        evidence=[Evidence(label="Traceback", detail="Error found")],
        risks=["Low risk"],
        recommended_action="Fix",
        fix_plan="Add null check",
        requires_human_approval=False,
        feishu_card={}
    )
    allowed, reason = should_auto_fix(decision)
    assert allowed is False
    assert "low confidence" in reason

def test_need_info_blocked():
    decision = Decision(
        decision=DecisionEnum.need_info,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="Test",
        root_cause_hypothesis="Test",
        evidence=[Evidence(label="Traceback", detail="Error found")],
        risks=["Low risk"],
        recommended_action="Fix",
        fix_plan="Add null check",
        requires_human_approval=False,
        feishu_card={}
    )
    allowed, reason = should_auto_fix(decision)
    assert allowed is False
    assert "not auto_fix" in reason

def test_high_risk_blocked():
    decision = Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="Test",
        root_cause_hypothesis="Test",
        evidence=[Evidence(label="Traceback", detail="Error found")],
        risks=["security vulnerability"],
        recommended_action="Fix",
        fix_plan="Add null check",
        requires_human_approval=False,
        feishu_card={}
    )
    allowed, reason = should_auto_fix(decision)
    assert allowed is False
    assert "high risk" in reason

def test_empty_evidence_blocked():
    decision = Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="Test",
        root_cause_hypothesis="Test",
        evidence=[],
        risks=["Low risk"],
        recommended_action="Fix",
        fix_plan="Add null check",
        requires_human_approval=False,
        feishu_card={}
    )
    allowed, reason = should_auto_fix(decision)
    assert allowed is False
    assert "no evidence" in reason

def test_requires_approval_blocked():
    decision = Decision(
        decision=DecisionEnum.auto_fix,
        confidence=ConfidenceEnum.high,
        severity=SeverityEnum.p1,
        incident_type=IncidentTypeEnum.runtime_exception,
        summary="Test",
        root_cause_hypothesis="Test",
        evidence=[Evidence(label="Traceback", detail="Error found")],
        risks=["Low risk"],
        recommended_action="Fix",
        fix_plan="Add null check",
        requires_human_approval=True,
        feishu_card={}
    )
    allowed, reason = should_auto_fix(decision)
    assert allowed is False
    assert "requires human approval" in reason
