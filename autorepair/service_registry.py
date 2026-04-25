import os
import yaml
from typing import List, Optional
from pathlib import Path
from autorepair.schemas import TargetService

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "services.yaml"
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def load_services(config_path: Optional[str | Path] = None) -> List[TargetService]:
    """加载所有服务配置"""
    config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    
    if not config_path.exists():
        raise FileNotFoundError(f"服务配置文件不存在: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    services = []
    for service_config in config.get("services", []):
        # 解析相对路径为绝对路径
        repo_path = PROJECT_ROOT / Path(service_config.pop("repo_path"))
        log_paths = [str(PROJECT_ROOT / Path(log_path)) for log_path in service_config.pop("log_paths", [])]
        
        service = TargetService(
            repo_path=str(repo_path.resolve()),
            log_paths=log_paths,
            **service_config
        )
        services.append(service)
    
    return services


def get_service(service_id: str, config_path: Optional[str | Path] = None) -> TargetService:
    """根据service_id获取服务配置"""
    services = load_services(config_path)
    for service in services:
        if service.service_id == service_id:
            return service
    raise ValueError(f"未找到服务: {service_id}")


def get_default_service(config_path: Optional[str | Path] = None) -> TargetService:
    """获取默认服务（第一个服务）"""
    services = load_services(config_path)
    if not services:
        raise ValueError("没有配置任何服务")
    return services[0]
