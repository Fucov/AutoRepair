import tempfile
from pathlib import Path
from unittest.mock import patch
from autorepair.repair.repo_lock import acquire_repo_lock


def test_repo_lock_prevents_concurrent_access():
    with acquire_repo_lock("test-repo") as lock1:
        assert lock1.acquired is True
        with acquire_repo_lock("test-repo") as lock2:
            assert lock2.acquired is False
