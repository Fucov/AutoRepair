import json
from pathlib import Path
from typing import Dict, Optional

from .config import PROJECT_ROOT

DEFAULT_WATCH_STATE_PATH = PROJECT_ROOT / "autorepair" / "records" / "watch_state.json"


def _ensure_path_exists(path: Path) -> None:
    """确保路径的父目录存在"""
    path.parent.mkdir(parents=True, exist_ok=True)


def load_watch_state(path: Optional[str | Path] = None) -> Dict:
    """
    加载监控状态
    :param path: 可选自定义状态文件路径
    :return: 状态字典，文件不存在则返回空
    """
    file_path = Path(path) if path else DEFAULT_WATCH_STATE_PATH
    if not file_path.exists():
        return {}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_watch_state(state: Dict, path: Optional[str | Path] = None) -> None:
    """
    保存监控状态
    :param state: 状态字典
    :param path: 可选自定义状态文件路径
    """
    file_path = Path(path) if path else DEFAULT_WATCH_STATE_PATH
    _ensure_path_exists(file_path)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"保存watch_state失败: {str(e)}")


def get_log_offset(log_path: str, state_path: Optional[str | Path] = None) -> int:
    """
    获取指定日志文件的读取偏移量
    :param log_path: 日志文件路径
    :param state_path: 可选自定义状态文件路径
    :return: 偏移量，日志被截断时返回0
    """
    state = load_watch_state(state_path)
    log_key = str(Path(log_path).resolve())
    
    saved_value = state.get("log_offsets", {}).get(log_key, 0)
    if isinstance(saved_value, dict):
        saved_offset = int(saved_value.get("offset", 0))
        saved_size = int(saved_value.get("size", saved_offset))
    else:
        saved_offset = int(saved_value or 0)
        saved_size = None
    
    # 检查当前日志文件大小，如果小于保存的偏移量，说明日志被截断
    try:
        current_size = Path(log_path).stat().st_size
        if saved_size is not None and current_size < saved_size:
            return 0
    except FileNotFoundError:
        return 0
    
    return saved_offset


def set_log_offset(log_path: str, offset: int, state_path: Optional[str | Path] = None) -> None:
    """
    设置指定日志文件的读取偏移量
    :param log_path: 日志文件路径
    :param offset: 新的偏移量
    :param state_path: 可选自定义状态文件路径
    """
    state = load_watch_state(state_path)
    log_key = str(Path(log_path).resolve())
    
    if "log_offsets" not in state:
        state["log_offsets"] = {}
    
    try:
        current_size = Path(log_path).stat().st_size
    except FileNotFoundError:
        current_size = offset

    state["log_offsets"][log_key] = {"offset": offset, "size": current_size}
    save_watch_state(state, state_path)
