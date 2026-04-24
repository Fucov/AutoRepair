import tempfile
from pathlib import Path
from autorepair.watch_state import load_watch_state, save_watch_state, get_log_offset, set_log_offset


def test_load_save_watch_state():
    """测试加载和保存状态"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        temp_path = Path(f.name)
    
    try:
        # 保存状态
        state = {"log_offsets": {"/test/path.log": 1234}}
        save_watch_state(state, temp_path)
        
        # 加载状态
        loaded = load_watch_state(temp_path)
        assert loaded == state
    finally:
        temp_path.unlink()


def test_get_set_log_offset():
    """测试获取和设置日志偏移量"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f_state:
        state_path = Path(f_state.name)
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f_log:
        log_path = Path(f_log.name)
        f_log.write("test content")
    
    try:
        # 设置偏移量
        set_log_offset(str(log_path), 5678, state_path)
        
        # 获取偏移量
        offset = get_log_offset(str(log_path), state_path)
        assert offset == 5678
    finally:
        state_path.unlink()
        log_path.unlink()


def test_get_log_offset_truncated():
    """测试日志被截断时偏移量重置为0"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f_state:
        state_path = Path(f_state.name)
    
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f_log:
        log_path = Path(f_log.name)
        # 写入长内容
        long_content = "x" * 1000
        f_log.write(long_content)
    
    try:
        # 设置大偏移量
        set_log_offset(str(log_path), 1000, state_path)
        
        # 截断文件，写入短内容
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("short")
        
        # 获取偏移量应该重置为0
        offset = get_log_offset(str(log_path), state_path)
        assert offset == 0
    finally:
        state_path.unlink()
        log_path.unlink()


def test_load_watch_state_not_exist():
    """测试状态文件不存在时返回空字典"""
    state = load_watch_state("/non/existent/state.json")
    assert state == {}
