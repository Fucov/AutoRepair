import pytest

from autorepair.repair.git_workspace import (
    assert_safe_cleanup_branch,
    build_repair_branch,
    validate_repair_branch,
)


def test_build_repair_branch_uses_autorepair_prefix():
    branch = build_repair_branch("INC-20260428-abcdef", "Ticket SLA TypeError")

    assert branch.startswith("autorepair/inc-20260428-abcdef-")
    assert "ticket-sla-typeerror" in branch


def test_validate_repair_branch_rejects_main_master_and_non_autorepair():
    for branch in ["main", "master", "develop", "feature/bugfix"]:
        with pytest.raises(ValueError):
            validate_repair_branch(branch)


def test_safe_cleanup_only_allows_autorepair_branches():
    assert_safe_cleanup_branch("autorepair/inc-abc-bug")
    for branch in ["main", "master", "develop", "feature/bugfix"]:
        with pytest.raises(ValueError):
            assert_safe_cleanup_branch(branch)
