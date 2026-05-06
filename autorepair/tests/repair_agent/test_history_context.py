from unittest.mock import patch, MagicMock

from autorepair.repair_agent.history_context import HistoryContext, collect_history_context


def test_collect_history_context_basic(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def foo():\n    return 1\n")
    ctx = collect_history_context(str(tmp_path), ["src/app.py"], line_no=1)
    assert isinstance(ctx, HistoryContext)
    assert ctx.file == "src/app.py"


def test_collect_history_context_empty_files():
    ctx = collect_history_context("/tmp/wt", [], line_no=None)
    assert isinstance(ctx, HistoryContext)
    assert ctx.file == ""


def test_git_command_failure_no_crash():
    ctx = collect_history_context("/nonexistent/path", ["some_file.py"], line_no=5)
    assert isinstance(ctx, HistoryContext)
    assert ctx.recent_commits == []
    assert ctx.blame_around_line is None
    assert ctx.last_modifier_summary == ""


def test_git_log_failure_returns_empty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result_history = collect_history_context("/tmp", ["file.py"])
        assert result_history.recent_commits == []


def test_git_blame_failure_returns_none():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result_history = collect_history_context("/tmp", ["file.py"], line_no=10)
        assert result_history.blame_around_line is None


def test_history_context_with_no_line():
    ctx = collect_history_context("/nonexistent", ["file.py"], line_no=None)
    assert ctx.blame_around_line is None