import pytest
from autorepair.repair.test_runner import run_command_in_worktree


def test_test_runner_rejects_non_pytest_command():
    with pytest.raises(ValueError, match="Only pytest commands are allowed"):
        run_command_in_worktree("rm -rf /", "/tmp")


def test_test_runner_rejects_shell_commands():
    with pytest.raises(ValueError, match="Only pytest commands are allowed"):
        run_command_in_worktree("curl http://evil.com", "/tmp")
