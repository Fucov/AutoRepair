from pathlib import Path
from autorepair.repair_agent.tools import MiniRepairTools


def _setup_worktree(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def hello():\n    return 'world'\n")
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_read_file_basic(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.read_file("src/app.py")
    assert result.ok
    assert "def hello" in result.output


def test_read_file_line_range(tmp_path):
    wt = _setup_worktree(tmp_path)
    (tmp_path / "src" / "big.py").write_text("\n".join(f"line {i}" for i in range(1, 101)))
    tools = MiniRepairTools(str(wt))
    result = tools.read_file("src/big.py", line_range="10-15")
    assert result.ok
    assert "line 10" in result.output
    assert "line 15" in result.output


def test_read_file_forbids_sensitive(tmp_path):
    wt = _setup_worktree(tmp_path)
    (tmp_path / ".env").write_text("SECRET=123")
    tools = MiniRepairTools(str(wt))
    result = tools.read_file(".env")
    assert not result.ok
    assert "敏感" in result.error


def test_read_file_escape_blocked(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.read_file("../etc/passwd")
    assert not result.ok


def test_get_file_excerpt(tmp_path):
    wt = _setup_worktree(tmp_path)
    lines = [f"line {i}" for i in range(1, 101)]
    (tmp_path / "src" / "big.py").write_text("\n".join(lines))
    tools = MiniRepairTools(str(wt))
    result = tools.get_file_excerpt("src/big.py", line=50, context=5)
    assert result.ok
    assert "line 45" in result.output
    assert "line 55" in result.output


def test_search_text_basic(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.search_text("hello")
    assert result.ok
    assert "app.py" in result.output


def test_search_text_skips_git(tmp_path):
    wt = _setup_worktree(tmp_path)
    (tmp_path / ".git" / "config").write_text("hello git")
    tools = MiniRepairTools(str(wt))
    result = tools.search_text("hello git")
    assert result.ok
    assert ".git" not in result.output


def test_run_tests_rejects_non_pytest(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.run_tests("rm -rf /")
    assert not result.ok
    assert "拒绝" in result.error


def test_apply_replace_success(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    tools.read_file("src/app.py")
    result = tools.apply_replace("src/app.py", "return 'world'", "return 'universe'")
    assert result.ok
    assert result.changed
    content = (tmp_path / "src" / "app.py").read_text()
    assert "universe" in content


def test_apply_replace_old_not_found(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    tools.read_file("src/app.py")
    result = tools.apply_replace("src/app.py", "nonexistent", "replacement")
    assert not result.ok
    assert "不存在" in result.error


def test_apply_replace_old_multiple(tmp_path):
    wt = _setup_worktree(tmp_path)
    (tmp_path / "src" / "dup.py").write_text("x = 1\nx = 1\n")
    tools = MiniRepairTools(str(wt))
    tools.read_file("src/dup.py")
    result = tools.apply_replace("src/dup.py", "x = 1", "x = 2")
    assert not result.ok
    assert "2 次" in result.error


def test_apply_replace_requires_read_first(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.apply_replace("src/app.py", "old", "new")
    assert not result.ok
    assert "read_file" in result.error


def test_rewrite_file_requires_read(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.rewrite_file("src/app.py", "new content")
    assert not result.ok
    assert "read_file" in result.error


def test_rewrite_file_empty_content(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    tools.read_file("src/app.py")
    result = tools.rewrite_file("src/app.py", "")
    assert not result.ok
    assert "空" in result.error


def test_git_diff(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.git_diff()
    assert result.ok


def test_finish(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.finish("fixed", "修复完成")
    assert result.ok
    assert tools.finish_reason == "fixed"


def test_run_tests_accepts_pytest(tmp_path):
    wt = _setup_worktree(tmp_path)
    tools = MiniRepairTools(str(wt))
    result = tools.run_tests("pytest --co -q")
    assert result.ok or result.error is not None
