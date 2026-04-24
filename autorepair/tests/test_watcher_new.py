import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from autorepair.watcher import scan_new_log_events_once
from autorepair.incident_store import DEFAULT_INCIDENT_PATH
from autorepair.watch_state import DEFAULT_WATCH_STATE_PATH


SAMPLE_LOG_MULTIPLE_ERRORS = """2024-05-01 12:00:00 - INFO - Request started
Traceback (most recent call last):
  File "demo_service/app.py", line 37, in get_user_profile
    return build_user_profile(user_id)
  File "demo_service/service.py", line 11, in build_user_profile
    "id": user["id"],
TypeError: 'NoneType' object is not subscriptable

2024-05-01 12:00:01 - INFO - Another request
Traceback (most recent call last):
  File "demo_service/app.py", line 179, in preview_order
    return calculate_order_discount(request)
  File "demo_service/order_service.py", line 16, in calculate_order_discount
    discount_rate = request.discount_amount / request.total_amount
ZeroDivisionError: division by zero
"""

SAMPLE_LOG_SAME_ERROR_TWICE = """2024-05-01 12:00:00 - INFO - Request started
Traceback (most recent call last):
  File "demo_service/service.py", line 11, in build_user_profile
    "id": user["id"],
TypeError: 'NoneType' object is not subscriptable

2024-05-01 12:00:01 - INFO - Another request
Traceback (most recent call last):
  File "demo_service/service.py", line 11, in build_user_profile
    "id": user["id"],
TypeError: 'NoneType' object is not subscriptable
"""


def test_scan_new_log_events_once_two_different_errors():
    """测试扫描到两个不同错误，返回两个created"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f_log:
        f_log.write(SAMPLE_LOG_MULTIPLE_ERRORS)
        log_path = Path(f_log.name)
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f_incident:
        incident_path = Path(f_incident.name)
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f_state:
        state_path = Path(f_state.name)
    
    try:
        with patch('autorepair.watcher.DEFAULT_INCIDENT_PATH', incident_path), \
             patch('autorepair.watcher.DEFAULT_WATCH_STATE_PATH', state_path):
            
            results = scan_new_log_events_once(log_path)
            assert len(results) == 2
            assert results[0][1] == "created"  # TypeError
            assert results[1][1] == "created"  # ZeroDivisionError
    finally:
        log_path.unlink()
        incident_path.unlink()
        state_path.unlink()


def test_scan_new_log_events_once_same_error_twice():
    """测试同一个错误出现两次，返回created和updated"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f_log:
        f_log.write(SAMPLE_LOG_SAME_ERROR_TWICE)
        log_path = Path(f_log.name)
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f_incident:
        incident_path = Path(f_incident.name)
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f_state:
        state_path = Path(f_state.name)
    
    try:
        with patch('autorepair.watcher.DEFAULT_INCIDENT_PATH', incident_path), \
             patch('autorepair.watcher.DEFAULT_WATCH_STATE_PATH', state_path):
            
            results = scan_new_log_events_once(log_path)
            assert len(results) == 2
            assert results[0][1] == "created"
            assert results[1][1] == "updated"
            assert results[1][0].occurrence_count == 2
    finally:
        log_path.unlink()
        incident_path.unlink()
        state_path.unlink()
