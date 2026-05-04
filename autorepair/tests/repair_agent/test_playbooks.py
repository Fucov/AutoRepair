import subprocess
from pathlib import Path
from unittest.mock import patch

from autorepair.repair_agent.schemas import RepairAgentContext
from autorepair.repair_agent.tools import MiniRepairTools
from autorepair.repair_agent.playbooks import try_apply_known_playbook


def test_timezone_playbook_fixes_bug(tmp_path):
    src = tmp_path / "demo_service" / "ticket_service.py"
    src.parent.mkdir(parents=True)
    src.write_text(
        "from datetime import datetime\n"
        "\n"
        "def submit_ticket(payload):\n"
        "    deadline = datetime.fromisoformat(payload['sla_deadline'])\n"
        "    if deadline < datetime.utcnow():\n"
        "        return False\n"
        "    return True\n"
    )

    ctx = RepairAgentContext(
        job_id="JOB-TZ",
        incident_id="INC-TZ",
        worktree_path=str(tmp_path),
        error_type="TypeError",
        error_message="can't compare offset-naive and offset-aware datetimes",
        suspected_file="demo_service/ticket_service.py",
        target_test_command="pytest --co -q",
        full_test_command="pytest --co -q",
    )
    tools = MiniRepairTools(str(tmp_path))

    with patch.object(tools, "run_tests") as mock_run:
        mock_run.return_value = type("R", (), {"ok": True, "output": "passed", "error": None})()
        result = try_apply_known_playbook(ctx, tools)

    assert result is not None
    assert result.status == "fixed"
    content = src.read_text()
    assert "timezone" in content
    assert "utcnow" not in content


def test_timezone_playbook_returns_none_for_unmatched(tmp_path):
    ctx = RepairAgentContext(
        job_id="JOB-X",
        incident_id="INC-X",
        worktree_path=str(tmp_path),
        error_type="AttributeError",
        error_message="'object' has no attribute 'foo'",
        suspected_file="src/main.py",
    )
    tools = MiniRepairTools(str(tmp_path))
    result = try_apply_known_playbook(ctx, tools)
    assert result is None
