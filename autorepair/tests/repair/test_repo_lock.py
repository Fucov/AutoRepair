import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepair.repair.repo_lock import acquire_repo_lock


def test_repo_lock_blocks_second_same_repo_holder():
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("autorepair.repair.repo_lock.DEFAULT_LOCK_DIR", Path(temp_dir)):
            with acquire_repo_lock("owner/repo") as first:
                assert first.acquired is True
                with acquire_repo_lock("owner/repo") as second:
                    assert second.acquired is False

            with acquire_repo_lock("owner/repo") as third:
                assert third.acquired is True
