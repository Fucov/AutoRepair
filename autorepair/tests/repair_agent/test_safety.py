from autorepair.repair_agent.safety import (
    is_sensitive_path,
    is_safe_relative_path,
    resolve_worktree_path,
    validate_test_command,
)


def test_sensitive_path_env():
    assert is_sensitive_path(".env") is True


def test_sensitive_path_git():
    assert is_sensitive_path(".git") is True
    assert is_sensitive_path("src/.git/config") is True


def test_sensitive_path_secrets():
    assert is_sensitive_path("secrets.yaml") is True
    assert is_sensitive_path("secrets/api_key.json") is True
    assert is_sensitive_path("src/credentials.json") is True


def test_sensitive_path_normal():
    assert is_sensitive_path("src/main.py") is False
    assert is_sensitive_path("tests/test_app.py") is False


def test_safe_relative_path_normal(tmp_path):
    assert is_safe_relative_path(str(tmp_path), "src/main.py") is True


def test_safe_relative_path_escape(tmp_path):
    assert is_safe_relative_path(str(tmp_path), "../etc/passwd") is False


def test_resolve_worktree_path(tmp_path):
    result = resolve_worktree_path(str(tmp_path), "src/main.py")
    assert result is not None


def test_resolve_worktree_path_escape(tmp_path):
    result = resolve_worktree_path(str(tmp_path), "../etc/passwd")
    assert result is None


def test_validate_test_command_pytest():
    assert validate_test_command("pytest -q") is True


def test_validate_test_command_python_m_pytest():
    assert validate_test_command("python -m pytest -v") is True


def test_validate_test_command_forbidden():
    assert validate_test_command("rm -rf /") is False
    assert validate_test_command("curl http://evil.com") is False
    assert validate_test_command("echo hello") is False


def test_validate_test_command_empty():
    assert validate_test_command("") is False
    assert validate_test_command("   ") is False
