import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepair.adapters.github import _load_mock_issues
from autorepair.issue_manager import ensure_issue_for_incident
from autorepair.schemas import ErrorSummary, Incident, TargetService


def _incident(occurrence_count: int = 1) -> Incident:
    return Incident(
        incident_id="INC-20260428-001",
        source="local_log",
        service="demo_service",
        error_summary=ErrorSummary(
            error_type="TypeError",
            message="can't compare offset-naive and offset-aware datetimes",
            suspected_file="demo_service/ticket_service.py",
            line_no=42,
            function="create_ticket",
            fingerprint="fp-ticket-sla",
        ),
        raw_traceback="Traceback\nTypeError: can't compare offset-naive and offset-aware datetimes",
        created_at="2026-04-28T12:00:00",
        updated_at="2026-04-28T12:00:00",
        occurrence_count=occurrence_count,
    )


def _service() -> TargetService:
    return TargetService(
        service_id="acme-supportdesk-lite",
        name="Acme SupportDesk Lite",
        repo_path=".",
        log_paths=[],
        test_command="pytest -q",
    )


def test_ensure_issue_for_incident_creates_standard_issue():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", temp_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""):
            issue_ref = ensure_issue_for_incident(_incident(), _service())

            issues = _load_mock_issues()
            assert issue_ref.number == issues[0]["number"]
            assert "[AutoRepair][Runtime][P1] Acme SupportDesk Lite" in issues[0]["title"]
            assert "TypeError at demo_service/ticket_service.py:42" in issues[0]["title"]
            assert "Incident ID: INC-20260428-001" in issues[0]["body"]
            assert "Service ID: acme-supportdesk-lite" in issues[0]["body"]
            assert "Fingerprint: fp-ticket-sla" in issues[0]["body"]
            assert "## Impact" in issues[0]["body"]
            assert "## AutoRepair Next Steps" in issues[0]["body"]
            assert "Traceback" in issues[0]["body"]
            assert issues[0]["assignees"] == ["AutoRepair"]
            assert set(["bug", "AutoRepair", "source:runtime", "autorepair:triage"]).issubset(issues[0]["labels"])
    finally:
        temp_path.unlink()


def test_ensure_issue_for_incident_links_existing_issue_by_fingerprint():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        temp_path = Path(f.name)

    try:
        with patch("autorepair.adapters.github.MOCK_GITHUB_ISSUES_PATH", temp_path), \
             patch("autorepair.adapters.github.GITHUB_TOKEN", ""):
            first = ensure_issue_for_incident(_incident(), _service())
            second = ensure_issue_for_incident(_incident(occurrence_count=3), _service())

            issues = _load_mock_issues()
            assert second.number == first.number
            assert len(issues) == 1
            assert issues[0]["comments"][0]["body"].find("occurrence_count=3") >= 0
    finally:
        temp_path.unlink()
