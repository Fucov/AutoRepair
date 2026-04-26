import os
import re
from typing import List
from autorepair.schemas import Incident
from autorepair.agent.triage.decision_schema import Evidence

TRACEBACK_PATTERN = re.compile(r'File "([^"]+)", line (\d+), in ([^\n]+)')

def collect_incident_evidence(incident: Incident) -> List[Evidence]:
    """
    Collect structured evidence from an incident for triage.
    """
    evidence: List[Evidence] = []
    git_sha = None  # Will be populated from context
    
    # Add traceback evidence if present
    if incident.raw_traceback:
        # Extract file and line from traceback
        match = TRACEBACK_PATTERN.search(incident.raw_traceback)
        file_path = match.group(1) if match else None
        line_number = int(match.group(2)) if match else None
        
        evidence.append(Evidence(
            label="Runtime Traceback",
            detail=incident.raw_traceback.strip(),
            file=file_path,
            line=line_number,
            sha=git_sha
        ))
    
    # Add error summary evidence
    if incident.error_summary:
        evidence.append(Evidence(
            label="Error Summary",
            detail=f"{incident.error_summary.error_type}: {incident.error_summary.message}",
            file=incident.error_summary.suspected_file,
            line=incident.error_summary.line_no,
            sha=git_sha
        ))
    
    # Add GitHub issue evidence if present
    if incident.source == "github_issue" and incident.issue_url:
        evidence.append(Evidence(
            label="GitHub Issue",
            detail=f"Issue #{incident.issue_number}: {incident.issue_url}",
            sha=git_sha
        ))
    
    return evidence
