import logging
from pathlib import Path
from autorepair.config import LOG_PATH


def setup_logging():
    """
    配置日志系统，确保日志包含完整 Traceback 并写入文件
    避免重复注册handler导致日志重复
    """
    root_logger = logging.getLogger()
    
    # 已经配置过handler则直接返回，避免重复注册
    if root_logger.handlers:
        return
    
    # 自动创建 logs 目录
    log_dir = LOG_PATH.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    
    # 屏蔽 uvicorn 冗余日志
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
