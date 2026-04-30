from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn
from pathlib import Path
import sys
import os

# 导入现有统计模块
from autorepair.dashboard.stats import (
    get_system_stats,
    get_incident_list,
    get_repair_job_list,
    get_issue_list,
    get_pr_list
)
# 导入核心功能模块
from autorepair.watcher import scan_latest_log_once
# from autorepair.issue_manager import scan_issues
# from autorepair.repair.orchestrator import run_repair_cycle
# from autorepair.adapters.github import sync_pr_status
# from autorepair.cards.variables import build_periodic_digest_variables
# from autorepair.cards import send_card
from autorepair.config import config, LOG_PATH

app = FastAPI(title="FeishuAutoRepair Dashboard", version="1.0.0")

# 静态文件托管
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 首页路由
@app.get("/")
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "FeishuAutoRepair Dashboard API"}

# 统计接口
@app.get("/api/stats")
async def api_get_stats() -> Dict[str, Any]:
    """获取系统统计数据"""
    return get_system_stats()

@app.get("/api/incidents")
async def api_get_incidents(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    """获取Incident列表"""
    return get_incident_list(limit=limit)

@app.get("/api/issues")
async def api_get_issues(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    """获取Issue列表"""
    return get_issue_list(limit=limit)

@app.get("/api/repair_jobs")
async def api_get_repair_jobs(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    """获取修复任务列表"""
    return get_repair_job_list(limit=limit)

@app.get("/api/prs")
async def api_get_prs(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    """获取PR列表"""
    return get_pr_list(limit=limit)

# 手动触发接口
class TriggerResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@app.post("/api/trigger/scan_logs", response_model=TriggerResponse)
async def api_trigger_scan_logs():
    """手动触发日志扫描"""
    try:
        result = scan_latest_log_once()
        return TriggerResponse(
            success=True,
            message="日志扫描完成",
            data={"incidents_found": 1 if result else 0}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"日志扫描失败: {str(e)}")

@app.post("/api/trigger/scan_issues", response_model=TriggerResponse)
async def api_trigger_scan_issues():
    """手动触发Issue扫描（待实现）"""
    try:
        # result = scan_issues()
        return TriggerResponse(
            success=True,
            message="Issue扫描功能待实现",
            data={"issues_found": 0}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Issue扫描失败: {str(e)}")

@app.post("/api/trigger/run_repair", response_model=TriggerResponse)
async def api_trigger_run_repair():
    """手动触发修复任务（待实现）"""
    try:
        # result = run_repair_cycle()
        return TriggerResponse(
            success=True,
            message="修复任务执行功能待实现",
            data={"jobs_created": 0}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修复任务执行失败: {str(e)}")

@app.post("/api/trigger/sync_prs", response_model=TriggerResponse)
async def api_trigger_sync_prs():
    """手动触发PR状态同步（待实现）"""
    try:
        # result = sync_pr_status()
        return TriggerResponse(
            success=True,
            message="PR状态同步功能待实现",
            data={"updated_prs": 0}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PR状态同步失败: {str(e)}")

@app.post("/api/trigger/send_digest", response_model=TriggerResponse)
async def api_trigger_send_digest():
    """手动发送统计摘要（待实现）"""
    try:
        # variables = build_periodic_digest_variables()
        # await send_card("periodic_digest", variables)
        return TriggerResponse(
            success=True,
            message="统计摘要发送功能待实现"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"统计摘要发送失败: {str(e)}")

# 配置接口
@app.get("/api/config")
async def api_get_config() -> Dict[str, Any]:
    """获取系统配置"""
    return {
        "FEISHU_API_BASE_URL": config.FEISHU_API_BASE_URL,
        "FEISHU_APP_ID": config.FEISHU_APP_ID,
        "FEISHU_CHAT_ID": config.FEISHU_CHAT_ID,
        "GITHUB_API_BASE_URL": config.GITHUB_API_BASE_URL,
        "GITHUB_OWNER": config.GITHUB_OWNER,
        "GITHUB_REPO": config.GITHUB_REPO,
        "GITHUB_ASSIGNEE": config.GITHUB_ASSIGNEE,
        "TEST_CMD": config.TEST_CMD,
        "LOG_PATH": str(LOG_PATH)
    }

class ConfigUpdate(BaseModel):
    key: str
    value: Any

@app.post("/api/config", response_model=TriggerResponse)
async def api_update_config(update: ConfigUpdate):
    """修改系统配置（待实现）"""
    try:
        return TriggerResponse(
            success=True,
            message="配置更新功能待实现"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")

def run_server(host: str = "0.0.0.0", port: int = 8888):
    """启动Dashboard服务器"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_server()
