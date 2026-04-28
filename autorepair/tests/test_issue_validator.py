from autorepair.adapters.github import GitHubIssue
from autorepair.issue_validator import validate_bug_issue


def test_validate_bug_issue_needs_info_when_body_has_no_repro_or_error():
    issue = GitHubIssue(
        number=1,
        title="[Bug] broken",
        body="It does not work. Please fix soon.",
        html_url="mock://local/issue/1",
        labels=["bug"],
        state="open",
    )

    result = validate_bug_issue(issue)

    assert result.is_valid is False
    assert result.evidence_level == "weak"
    assert "reproduction steps" in result.missing_fields
    assert "error message or traceback" in result.missing_fields
    assert "请补充" in result.suggested_comment


def test_validate_bug_issue_accepts_repro_expected_actual_and_error():
    issue = GitHubIssue(
        number=2,
        title="[Bug] ticket SLA TypeError",
        body="""## Service
Acme SupportDesk Lite

## Steps to Reproduce
1. Create a ticket with timezone-aware SLA deadline.

## Expected Behavior
Ticket is created.

## Actual Behavior
500 response.

## Error
TypeError: can't compare offset-naive and offset-aware datetimes
""",
        html_url="mock://local/issue/2",
        labels=["bug"],
        state="open",
    )

    result = validate_bug_issue(issue)

    assert result.is_valid is True
    assert result.evidence_level in {"enough", "strong"}
    assert result.missing_fields == []


def test_validate_bug_issue_rejects_high_risk_security_change():
    issue = GitHubIssue(
        number=3,
        title="[Bug] permissions broken",
        body="""## Steps to Reproduce
Log in as a normal user.

## Expected Behavior
No admin access.

## Actual Behavior
Permission system allows admin access. Please rewrite auth and rotate leaked secret.
""",
        html_url="mock://local/issue/3",
        labels=["bug"],
        state="open",
    )

    result = validate_bug_issue(issue)

    assert result.is_valid is False
    assert result.evidence_level == "strong"
    assert "high risk" in result.reason.lower()
