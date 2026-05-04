from pathlib import Path
from unittest.mock import MagicMock, patch

from autorepair.repair_agent.loop import MiniRepairAgent
from autorepair.repair_agent.schemas import RepairAgentContext, ToolResult
from autorepair.repair_agent.tools import MiniRepairTools


def _make_context(tmp_path: Path, target_cmd: str = "pytest -q") -> RepairAgentContext:
    return RepairAgentContext(
        job_id="JOB-LOOP",
        incident_id="INC-LOOP",
        worktree_path=str(tmp_path),
        error_type="TypeError",
        error_message="test error",
        suspected_file="src/app.py",
        target_test_command=target_cmd,
        full_test_command="pytest -q",
    )


def test_agent_fixed_flow(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def foo():\n    return 1\n")

    mock_llm = MagicMock()
    mock_llm.chat_json.side_effect = [
        {"tool": "read_file", "args": {"path": "src/app.py"}},
        {"tool": "apply_replace", "args": {"path": "src/app.py", "old": "return 1", "new": "return 2"}},
        {"tool": "finish", "args": {"status": "fixed", "summary": "fixed"}},
    ]

    agent = MiniRepairAgent(mock_llm)
    ctx = _make_context(tmp_path)

    with patch.object(MiniRepairAgent, "_dispatch_tool") as mock_dispatch:
        mock_dispatch.side_effect = [
            ToolResult(tool="read_file", ok=True, output="1: return 1"),
            ToolResult(tool="apply_replace", ok=True, output="ok", changed=True),
        ]

        with patch("autorepair.repair_agent.loop.save_repair_transcript"):
            result = agent.run(ctx)

    assert result.status == "fixed"


def test_agent_not_reproducible(tmp_path):
    mock_llm = MagicMock()
    agent = MiniRepairAgent(mock_llm)
    ctx = _make_context(tmp_path)

    with patch.object(MiniRepairTools, "run_tests") as mock_run:
        mock_run.return_value = ToolResult(tool="run_tests", ok=True, output="passed")

        with patch("autorepair.repair_agent.loop.save_repair_transcript"):
            result = agent.run(ctx)

    assert result.status == "not_reproducible"


def test_agent_retry_after_test_fail(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")

    mock_llm = MagicMock()
    mock_llm.chat_json.side_effect = [
        {"tool": "apply_replace", "args": {"path": "src/app.py", "old": "x = 1", "new": "x = 2"}},
        {"tool": "run_tests", "args": {"command": "pytest -q"}},
        {"tool": "apply_replace", "args": {"path": "src/app.py", "old": "x = 2", "new": "x = 3"}},
        {"tool": "run_tests", "args": {"command": "pytest -q"}},
        {"tool": "finish", "args": {"status": "fixed", "summary": "done"}},
    ]

    agent = MiniRepairAgent(mock_llm, max_retries=3)
    ctx = _make_context(tmp_path)

    call_count = 0

    def dispatch_side_effect(tools, call):
        nonlocal call_count
        call_count += 1
        if call.tool == "apply_replace":
            tools.read_file("src/app.py")
            (tmp_path / "src" / "app.py").write_text("x = 3\n")
            return ToolResult(tool="apply_replace", ok=True, output="ok", changed=True)
        if call.tool == "run_tests":
            if call_count <= 3:
                return ToolResult(tool="run_tests", ok=False, output="fail", error="fail")
            return ToolResult(tool="run_tests", ok=True, output="pass")
        return ToolResult(tool="finish", ok=True, output="done")

    with patch.object(MiniRepairAgent, "_dispatch_tool", side_effect=dispatch_side_effect):
        with patch("autorepair.repair_agent.loop.save_repair_transcript"):
            result = agent.run(ctx)

    assert result.status in ("fixed", "test_failed")


def test_agent_max_retries_returns_test_failed(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {"tool": "run_tests", "args": {"command": "pytest -q"}}

    agent = MiniRepairAgent(mock_llm, max_steps=10, max_retries=2)
    ctx = _make_context(tmp_path)

    with patch("autorepair.repair_agent.loop.save_repair_transcript"):
        result = agent.run(ctx)

    assert result.status == "test_failed"


def test_agent_needs_human(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")

    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {"tool": "finish", "args": {"status": "needs_human", "summary": "too complex"}}

    agent = MiniRepairAgent(mock_llm)
    ctx = _make_context(tmp_path)

    with patch("autorepair.repair_agent.loop.save_repair_transcript"):
        result = agent.run(ctx)

    assert result.status == "needs_human"


def test_agent_error_no_crash(tmp_path):
    mock_llm = MagicMock()
    mock_llm.chat_json.side_effect = RuntimeError("API down")

    agent = MiniRepairAgent(mock_llm)
    ctx = _make_context(tmp_path)

    with patch("autorepair.repair_agent.loop.save_repair_transcript"):
        result = agent.run(ctx)

    assert result.status == "agent_error"
    assert "API down" in (result.error or "")
