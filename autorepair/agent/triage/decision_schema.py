from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class DecisionEnum(str, Enum):
    auto_fix = "auto_fix"
    propose_fix = "propose_fix"
    need_info = "need_info"
    duplicate = "duplicate"
    cannot_reproduce = "cannot_reproduce"
    config_error = "config_error"
    external_dependency = "external_dependency"
    keep_open = "keep_open"
    escalate = "escalate"

class ConfidenceEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class SeverityEnum(str, Enum):
    p0 = "p0"
    p1 = "p1"
    p2 = "p2"
    p3 = "p3"

class IncidentTypeEnum(str, Enum):
    runtime_exception = "runtime_exception"
    test_failure = "test_failure"
    regression = "regression"
    dependency = "dependency"
    config = "config"
    flaky = "flaky"
    product_request = "product_request"
    unknown = "unknown"

class Evidence(BaseModel):
    label: str
    detail: str
    file: Optional[str] = None
    line: Optional[int] = None
    command: Optional[str] = None
    sha: Optional[str] = None

class Decision(BaseModel):
    decision: DecisionEnum
    confidence: ConfidenceEnum
    severity: SeverityEnum
    incident_type: IncidentTypeEnum
    summary: str
    root_cause_hypothesis: str
    evidence: List[Evidence] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommended_action: str
    fix_plan: Optional[str] = None
    requires_human_approval: bool = Field(default=False)
    feishu_card: Dict[str, Any] = Field(default_factory=dict)
