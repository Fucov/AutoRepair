import json
from unittest.mock import Mock, patch
from autorepair.agent.triage.triage_agent import run_triage
from autorepair.agent.triage.decision_schema import Decision, DecisionEnum, ConfidenceEnum

def test_triage_agent_parses_valid_json():
    mock_llm_response = json.dumps({
        "decision": "auto_fix",
        "confidence": "high",
        "severity": "p1",
        "incident_type": "runtime_exception",
        "summary": "Test incident",
        "root_cause_hypothesis": "Test cause",
        "evidence": [{"label": "Test", "detail": "Test detail"}],
        "risks": ["Low risk"],
        "recommended_action": "Fix",
        "fix_plan": "Test fix",
        "requires_human_approval": False,
        "feishu_card": {"title": "已完成诊断，准备自动修复"}
    })
    
    with patch('autorepair.agent.triage.triage_agent.call_llm', return_value=mock_llm_response):
        decision = run_triage(incident_context="Test context")
        assert isinstance(decision, Decision)
        assert decision.decision == DecisionEnum.auto_fix
        assert decision.confidence == ConfidenceEnum.high

def test_triage_agent_handles_invalid_json():
    with patch('autorepair.agent.triage.triage_agent.call_llm', return_value="Invalid json {"):
        decision = run_triage(incident_context="Test context")
        assert decision.decision == DecisionEnum.need_info
        assert "Failed to parse LLM response" in decision.summary
