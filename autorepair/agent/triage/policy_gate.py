from typing import Tuple
from autorepair.agent.triage.decision_schema import Decision, DecisionEnum, ConfidenceEnum

HIGH_RISK_KEYWORDS = {"security", "payment", "permission", "data_loss", "delete", "remove"}

def should_auto_fix(decision: Decision) -> Tuple[bool, str]:
    """
    Determines if an incident should enter the automatic repair pipeline.
    Returns (allowed: bool, blocked_reason: str)
    """
    # Check decision type
    if decision.decision != DecisionEnum.auto_fix:
        return False, f"Decision is {decision.decision}, not auto_fix"
    
    # Check confidence
    if decision.confidence != ConfidenceEnum.high:
        return False, f"Confidence is {decision.confidence}, not high"
    
    # Check evidence exists
    if not decision.evidence:
        return False, "No evidence provided to support auto fix"
    
    # Check fix plan exists
    if not decision.fix_plan:
        return False, "No fix plan provided"
    
    # Check human approval requirement
    if decision.requires_human_approval:
        return False, "Auto fix requires human approval"
    
    # Check for high risk keywords in risks
    for risk in decision.risks:
        risk_lower = risk.lower()
        for keyword in HIGH_RISK_KEYWORDS:
            if keyword in risk_lower:
                return False, f"High risk detected: {keyword} in risk description"
    
    # All checks passed
    return True, ""
