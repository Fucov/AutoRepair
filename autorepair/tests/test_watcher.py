import tempfile
from pathlib import Path
from unittest.mock import patch
from autorepair.watcher import scan_latest_log_once

SAMPLE_TRACEBACK = """Traceback (most recent call last):
  File "/demo_service/app.py", line 37, in get_user_profile
    return build_user_profile(user_id)
  File "/demo_service/service.py", line 11, in build_user_profile
    "id": user["id"],
TypeError: 'NoneType' object is not subscriptable
"""


def test_scan_latest_log_once_no_traceback():
    """测试没有Traceback时返回None"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        f.write("2024-05-01 12:00:00 - INFO - Normal log line\n")
        temp_path = Path(f.name)
    
    try:
        incident = scan_latest_log_once(str(temp_path))
        assert incident is None
    finally:
        temp_path.unlink()


@patch("autorepair.watcher.has_fingerprint", return_value=True)
def test_scan_latest_log_once_duplicate_fingerprint(mock_has_fingerprint):
    """测试指纹已存在时返回None（去重）"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        f.write(SAMPLE_TRACEBACK)
        temp_path = Path(f.name)
    
    try:
        incident = scan_latest_log_once(str(temp_path))
        assert incident is None
        mock_has_fingerprint.assert_called_once()
    finally:
        temp_path.unlink()
