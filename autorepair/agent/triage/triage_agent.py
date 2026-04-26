import json
import logging
from typing import Optional
from jinja2 import Template
from autorepair.agent.triage.triage_prompt import TRIAGE_PROMPT
from autorepair.agent.triage.decision_schema import Decision, DecisionEnum, ConfidenceEnum, SeverityEnum, IncidentTypeEnum

logger = logging.getLogger(__name__)

# Placeholder for LLM call - replace with actual LLM integration
def call_llm(prompt: str) -> str:
    """
    Call LLM with the given prompt and return the response.
    This is a placeholder - replace with actual LLM integration.
    """
    raise NotImplementedError("LLM integration not implemented yet")

def run_triage(incident_context: str) -> Decision:
    """
    Run triage on an incident, returns validated Decision object.
    """
    # Render prompt with incident context
    prompt = Template(TRIAGE_PROMPT).render(incident_context=incident_context)
    
    try:
        # Call LLM
        llm_response = call_llm(prompt)
        
        # Parse JSON response
        try:
            decision_data = json.loads(llm_response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return Decision(
                decision=DecisionEnum.need_info,
                confidence=ConfidenceEnum.low,
                severity=SeverityEnum.p3,
                incident_type=IncidentTypeEnum.unknown,
                summary=f"Failed to parse LLM response: {str(e)}",
                root_cause_hypothesis="LLM output was not valid JSON",
                evidence=[],
                risks=["LLM response parsing failed"],
                recommended_action="Review triage prompt and LLM output",
                requires_human_approval=True,
                feishu_card={"title": "诊断失败，需要人工处理"}
            )
        
        # Validate against schema
        try:
            decision = Decision(**decision_data)
            return decision
        except Exception as e:
            logger.error(f"Decision schema validation failed: {e}")
            return Decision(
                decision=DecisionEnum.need_info,
                confidence=ConfidenceEnum.low,
                severity=SeverityEnum.p3,
                incident_type=IncidentTypeEnum.unknown,
                summary=f"Decision schema validation failed: {str(e)}",
                root_cause_hypothesis="LLM output did not match expected schema",
                evidence=[],
                risks=["Schema validation failed"],
                recommended_action="Review triage prompt and LLM output",
                requires_human_approval=True,
                feishu_card={"title": "诊断失败，需要人工处理"}
            )
            
    except Exception as e:
        logger.error(f"Triage failed with unexpected error: {e}", exc_info=True)
        return Decision(
            decision=DecisionEnum.escalate,
            confidence=ConfidenceEnum.low,
            severity=SeverityEnum.p2,
            incident_type=IncidentTypeEnum.unknown,
            summary=f"Triage failed with error: {str(e)}",
            root_cause_hypothesis="Internal error in triage agent",
            evidence=[],
            risks=["Triage agent failure"],
            recommended_action="Check triage agent implementation",
            requires_human_approval=True,
            feishu_card={"title": "诊断系统异常，需要人工处理"}
        )
