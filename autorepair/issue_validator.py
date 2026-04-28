from __future__ import annotations

from pydantic import BaseModel

from autorepair.adapters.github import GitHubIssue


class IssueValidationResult(BaseModel):
    is_valid: bool
    reason: str
    missing_fields: list[str]
    evidence_level: str
    suggested_comment: str


HIGH_RISK_PATTERNS = [
    "security",
    "secret",
    "leaked",
    "credential",
    "permission",
    "auth",
    "production database",
    "drop database",
    "delete production",
]


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def _category_hits(title: str, body: str) -> dict[str, bool]:
    text = f"{title}\n{body}".lower()
    return {
        "service/module": _has_any(text, ["service", "module", "component", "demo_service", "acme", "ticket", "order", "profile"]),
        "reproduction steps": _has_any(text, ["steps to reproduce", "reproduce", "复现", "步骤", "1."]),
        "expected behavior": _has_any(text, ["expected behavior", "expected", "期望"]),
        "actual behavior": _has_any(text, ["actual behavior", "actual", "实际", "500", "failed", "broken"]),
        "error message or traceback": _has_any(text, ["traceback", "error", "exception", "typeerror", "zerodivisionerror", "stack trace"]),
        "failing test or command": _has_any(text, ["pytest", "failing test", "command", "test_", "测试失败"]),
    }


def _evidence_level(count: int) -> str:
    if count <= 0:
        return "none"
    if count <= 2:
        return "weak"
    if count <= 4:
        return "enough"
    return "strong"


def validate_bug_issue(issue: GitHubIssue) -> IssueValidationResult:
    labels = set(issue.labels)
    title = issue.title or ""
    body = issue.body or ""
    text = f"{title}\n{body}".lower()

    if "bug" not in labels and "[bug]" not in title.lower():
        return IssueValidationResult(
            is_valid=False,
            reason="Issue is not marked as a bug.",
            missing_fields=["bug label or [Bug] title"],
            evidence_level="none",
            suggested_comment="请将该问题标记为 bug，或在标题中包含 [Bug] 后再交给 AutoRepair 处理。",
        )

    blocked_status = labels.intersection({"autorepair:closed", "autorepair:repairing", "autorepair:pr-ready"})
    if blocked_status:
        status = sorted(blocked_status)[0]
        return IssueValidationResult(
            is_valid=False,
            reason=f"Issue already has status {status}.",
            missing_fields=[],
            evidence_level="enough",
            suggested_comment=f"AutoRepair 检测到该 Issue 已处于 `{status}` 状态，因此不会重复处理。",
        )

    hits = _category_hits(title, body)
    hit_count = sum(1 for present in hits.values() if present)
    missing = [name for name, present in hits.items() if not present]
    level = _evidence_level(hit_count)
    has_repro = hits["reproduction steps"]
    has_error = hits["error message or traceback"]

    high_risk = any(pattern in text for pattern in HIGH_RISK_PATTERNS)
    if high_risk:
        return IssueValidationResult(
            is_valid=False,
            reason="High risk issue requires human review.",
            missing_fields=[] if hit_count >= 3 else missing,
            evidence_level="strong" if hit_count >= 3 else level,
            suggested_comment="该 Issue 涉及安全、权限、密钥或生产数据等高风险内容，需要人工确认后再处理。",
        )

    if not has_repro and not has_error:
        return IssueValidationResult(
            is_valid=False,
            reason="Issue lacks both reproduction steps and error evidence.",
            missing_fields=["reproduction steps", "error message or traceback"],
            evidence_level=level,
            suggested_comment="请补充复现步骤以及错误信息或 traceback。AutoRepair 不会根据过少信息直接修复。",
        )

    if hit_count < 3:
        friendly_missing = ", ".join(missing[:3])
        return IssueValidationResult(
            is_valid=False,
            reason="Issue does not contain enough evidence for automatic triage.",
            missing_fields=missing,
            evidence_level=level,
            suggested_comment=f"请补充更多信息后再处理，建议至少补充：{friendly_missing}。",
        )

    return IssueValidationResult(
        is_valid=True,
        reason="Issue contains enough information for AutoRepair triage.",
        missing_fields=[],
        evidence_level=level,
        suggested_comment="AutoRepair 已收集到足够信息，将进入自动分诊流程。",
    )
