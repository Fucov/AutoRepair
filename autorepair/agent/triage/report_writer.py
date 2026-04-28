import os
import json
from pathlib import Path
from typing import Tuple
from autorepair.agent.triage.decision_schema import Decision

REPORT_DIR = Path(".agent/reports/items")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def write_triage_report(
    incident_id: str,
    incident_source: str,
    git_sha: str,
    decision: Decision,
    policy_passed: bool,
    feishu_message_id: str = None
) -> Tuple[str, str]:
    """
    Writes triage report and decision JSON to disk.
    Returns (markdown_report_path: str, decision_json_path: str)
    """
    base_path = REPORT_DIR / incident_id
    md_path = f"{base_path}.md"
    json_path = f"{base_path}.decision.json"
    
    # Write decision JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(decision.model_dump(), f, indent=2, ensure_ascii=False)
    
    # Generate Markdown report
    evidence_md = "\n".join([
        f"- **{e.label}**: {e.detail}" + 
        (f" ([{e.file}:{e.line}](file:///{os.path.abspath(e.file)}))" if e.file and e.line else "") +
        (f" (SHA: {e.sha})" if e.sha else "")
        for e in decision.evidence
    ])
    
    risks_md = "\n".join([f"- {r}" for r in decision.risks]) if decision.risks else "None"
    
    md_content = f"""# Incident Triage Report: {incident_id}

## Basic Information
- **Incident ID**: {incident_id}
- **Source**: {incident_source}
- **Git SHA**: {git_sha}
- **Decision**: {decision.decision.value}
- **Confidence**: {decision.confidence.value}
- **Severity**: {decision.severity.value}
- **Incident Type**: {decision.incident_type.value}
{ f"- **Feishu Message ID**: {feishu_message_id}" if feishu_message_id else "" }

## Summary
{decision.summary}

## Root Cause Hypothesis
{decision.root_cause_hypothesis}

## Evidence
{evidence_md}

## Risks
{risks_md}

## Recommended Action
{decision.recommended_action}

## Fix Plan
{decision.fix_plan if decision.fix_plan else "None"}

## Policy Gate Result
Policy gate result: {'✅ PASSED' if policy_passed else '❌ BLOCKED'}

{'✅ PASSED' if policy_passed else '❌ BLOCKED'}
"""
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    return str(md_path), str(json_path)
