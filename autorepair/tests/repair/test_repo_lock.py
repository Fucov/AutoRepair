import tempfile
from pathlib import Path
from unittest.mock import patch
from autorepair.repair.repo_lock import acquire_repo_lock, DEFAULT_LOCK_DIR


def test_repo_lock_prevents_concurrent_access():
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_lock_dir = Path(tmpdir) / "locks"
        with patch("autorepair.repair.repo_lock.DEFAULT_LOCK_DIR", temp_lock_dir):
            with acquire_repo_lock("test-repo") as lock1:
                assert lock1.acquired is True
                with acquire_repo_lock("test-repo") as lock2:
                    assert lock2.acquired is False
