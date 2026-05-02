from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
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
# 导入完整链路功能模块
from autorepair.watcher import scan_service_logs_once
from autorepair.service_registry import get_default_service
from autorepair.adapters.feishu import send_incident_card, send_template_card
from autorepair.adapters.github import list_open_bug_issues
from autorepair.issue_manager import ensure_issue_for_incident
from autorepair.incident_store import update_incident_fields
from autorepair.audit_store import append_audit_event
from autorepair.cards import (
    build_periodic_digest_variables,
    build_repair_plan_ready_variables,
    build_manual_intervention_variables,
)
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
    """手动触发日志扫描 - 完整链路：扫描日志→创建Incident→创建Issue→发送飞书卡片"""
    try:
        # 获取默认服务
        service = get_default_service()
        
        # 扫描服务日志
        results = scan_service_logs_once(service)
        if not results:
            return TriggerResponse(
                success=True,
                message="日志扫描完成，未发现新异常",
                data={
                    "incidents_created": 0,
                    "incidents_updated": 0,
                    "issues_created": 0,
                    "cards_sent": 0
                }
            )
        
        # 统计数据
        created_count = 0
        updated_count = 0
        feishu_sent_count = 0
        issue_created_count = 0
        details = []
        
        for incident, action in results:
            summary = incident.error_summary
            if action == "created":
                created_count += 1
                
                # 创建GitHub Issue
                issue_ref = ensure_issue_for_incident(incident, service)
                issue_url = issue_ref.html_url
                incident.issue_number = issue_ref.number
                incident.issue_url = issue_url
                
                # 持久化issue链接到incidents.jsonl
                update_incident_fields(
                    incident.incident_id,
                    issue_number=issue_ref.number,
                    issue_url=issue_url
                )
                
                if issue_url:
                    issue_created_count += 1
                    details.append(f"Created Issue: {issue_url}")
                
                # 发送飞书卡片
                send_result = send_incident_card(incident)
                if send_result:
                    feishu_sent_count += 1
                    append_audit_event(
                        "feishu_card_sent" if not send_result.get("mock") else "feishu_card_mocked",
                        incident.incident_id,
                        {"card_type": "incident_detected"}
                    )
                else:
                    append_audit_event("feishu_card_failed", incident.incident_id, {"card_type": "incident_detected"})

                # 记录审计
                append_audit_event("incident_created", incident.incident_id, {
                    "error_type": summary.error_type,
                    "service": incident.service,
                    "issue_url": issue_url
                })
                
                details.append(
                    f"[created] {incident.incident_id} {summary.error_type} "
                    f"{incident.service_name} occurrence_count={incident.occurrence_count}"
                )
                
            else:
                updated_count += 1
                details.append(
                    f"[updated] {incident.incident_id} occurrence_count={incident.occurrence_count}"
                )
        
        return TriggerResponse(
            success=True,
            message=f"日志扫描完成：创建{created_count}个Incident，更新{updated_count}个，创建{issue_created_count}个Issue，发送{feishu_sent_count}个飞书卡片",
            data={
                "incidents_created": created_count,
                "incidents_updated": updated_count,
                "issues_created": issue_created_count,
                "cards_sent": feishu_sent_count,
                "service": service.name,
                "details": details
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"日志扫描失败: {str(e)}")

@app.post("/api/trigger/scan_issues", response_model=TriggerResponse)
async def api_trigger_scan_issues():
    """手动触发Issue扫描 - 扫描GitHub上的open bug issues，判断是否适合自动修复"""
    try:
        service = get_default_service()
        issues = list_open_bug_issues()

        if not issues:
            return TriggerResponse(
                success=True,
                message="Issue扫描完成，未发现待处理的Bug Issue",
                data={
                    "issues_found": 0,
                    "suitable_for_fix": 0,
                    "manual_intervention": 0
                }
            )

        suitable_count = 0
        manual_count = 0
        details = []

        for issue in issues:
            issue_id = f"ISSUE-{issue.number}"
            labels = issue.labels

            # 检查是否适合自动修复
            if "bug" not in labels or "AutoRepair" not in labels:
                details.append(f"#{issue.number}: 缺少必要标签，跳过")
                continue

            if any(tag in labels for tag in ["invalid", "wontfix", "question"]):
                details.append(f"#{issue.number}: 标记为无需处理，跳过")
                continue

            # 判断是否包含可修复的错误类型
            keywords = ["TypeError", "AttributeError", "IndexError", "KeyError", "ZeroDivisionError"]
            has_error_keyword = any(kw.lower() in issue.title.lower() for kw in keywords)
            has_traceback = "Traceback" in issue.body or 'File "' in issue.body

            if has_error_keyword or has_traceback:
                suitable_count += 1
                variables = build_repair_plan_ready_variables(
                    incident_id=issue_id,
                    service_name=service.name,
                    root_cause="系统检测到可自动修复的代码错误",
                    fix_strategy="分析Traceback并生成修复补丁",
                    risk_level="低风险",
                    policy_summary="允许进入自动修复"
                )
                send_template_card("repair_plan_ready", variables)
                append_audit_event("repair_plan_generated", issue_id, {
                    "issue_number": issue.number,
                    "issue_url": issue.html_url
                })
                details.append(f"#{issue.number}: 适合自动修复，已发送修复计划卡片")
            else:
                manual_count += 1
                variables = build_manual_intervention_variables(
                    incident_id=issue_id,
                    service_name=service.name,
                    human_reason="该问题不适合自动修复，需要人工介入",
                    evidence_brief=issue.body[:100] if issue.body else "无详细描述",
                    next_action="请查看Issue详情并手动处理",
                )
                send_template_card("manual_intervention", variables)
                append_audit_event("manual_intervention_required", issue_id, {
                    "issue_number": issue.number,
                    "issue_url": issue.html_url
                })
                details.append(f"#{issue.number}: 需要人工介入，已发送通知卡片")

        return TriggerResponse(
            success=True,
            message=f"Issue扫描完成：发现{len(issues)}个Issue，{suitable_count}个适合修复，{manual_count}个需要人工介入",
            data={
                "issues_found": len(issues),
                "suitable_for_fix": suitable_count,
                "manual_intervention": manual_count,
                "details": details
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Issue扫描失败: {str(e)}")

@app.post("/api/trigger/run_repair", response_model=TriggerResponse)
async def api_trigger_run_repair():
    """手动触发修复任务 - 从queued队列中取出一个job执行完整修复链路"""
    try:
        from autorepair.repair.executor import execute_next_repair_job
        result = execute_next_repair_job()
        
        if result.error:
            return TriggerResponse(
                success=True,
                message=result.error,
                data={"job_id": result.job.job_id if result.job else None}
            )
        
        if result.job:
            return TriggerResponse(
                success=True,
                message=f"修复任务完成: {result.job.job_id}",
                data={
                    "job_id": result.job.job_id,
                    "status": result.job.status.value,
                    "pr_url": result.job.pr_url,
                    "pr_number": result.job.pr_number
                }
            )
        
        return TriggerResponse(
            success=True,
            message="没有待执行的修复任务",
            data={"jobs_created": 0}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修复任务执行失败: {str(e)}")

@app.post("/api/trigger/sync_prs", response_model=TriggerResponse)
async def api_trigger_sync_prs():
    """手动触发PR状态同步 - 扫描pr_created job，检查PR是否合并"""
    try:
        from autorepair.repair.job_store import DEFAULT_REPAIR_JOBS_PATH, load_repair_jobs
        from autorepair.repair.schemas import RepairJobStatus

        jobs = [job for job in load_repair_jobs(DEFAULT_REPAIR_JOBS_PATH) if job.status == RepairJobStatus.pr_created]
        if not jobs:
            return TriggerResponse(
                success=True,
                message="没有需要同步的PR状态",
                data={"updated_jobs": 0}
            )

        # 内联 sync_once 逻辑，避免跨包导入问题
        merged_count = 0
        closed_count = 0
        for job in jobs:
            from autorepair.adapters.github import get_pull_request, close_issue, comment_issue, replace_autorepair_status_label
            from autorepair.repair.job_store import update_repair_job
            if job.pr_number is None:
                continue
            pr = get_pull_request(job.pr_number)
            if pr is None or pr.state == "open":
                continue
            if pr.merged:
                comment_issue(job.issue_number, f"AutoRepair PR #{job.pr_number} has been merged. Closing this Issue.")
                close_issue(job.issue_number)
                replace_autorepair_status_label(job.issue_number, "autorepair:closed")
                update_repair_job(job.job_id, path=DEFAULT_REPAIR_JOBS_PATH, status=RepairJobStatus.merged)
                merged_count += 1
            else:
                comment_issue(job.issue_number, f"AutoRepair PR #{job.pr_number} was closed without merge.")
                replace_autorepair_status_label(job.issue_number, "autorepair:human-required")
                update_repair_job(job.job_id, path=DEFAULT_REPAIR_JOBS_PATH, status=RepairJobStatus.human_required, last_error="PR closed without merge")
                closed_count += 1

        return TriggerResponse(
            success=True,
            message=f"PR状态同步完成：合并{merged_count}个，关闭{closed_count}个",
            data={
                "merged": merged_count,
                "closed_without_merge": closed_count,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PR状态同步失败: {str(e)}")

@app.post("/api/trigger/send_digest", response_model=TriggerResponse)
async def api_trigger_send_digest():
    """手动发送统计摘要 - 基于当前系统数据生成飞书摘要卡片"""
    try:
        service = get_default_service()
        current_stats = get_system_stats()
        summary = current_stats["summary"]
        now = datetime.now()

        total = summary["total_incidents"]
        fixed = summary["successful_repairs"]
        failed = summary["failed_repairs"]
        manual = summary["failed_repairs"]
        success_rate = f"{summary['repair_success_rate']}%"

        summary_sentence = (
            f"当前共发现 {total} 个问题，自动修复成功 {fixed} 个，{manual} 个需人工介入"
        )

        variables = build_periodic_digest_variables(
            period_label=now.strftime("%Y-%m-%d"),
            summary_sentence=summary_sentence,
            metric_total=total,
            metric_fixed=fixed,
            metric_manual=manual,
            success_rate=success_rate,
            avg_triage_time="N/A",
            avg_repair_time="N/A",
            top_errors_text="错误类型: " + ", ".join(
                list(current_stats["distributions"]["error_type"].keys())[:5]
            ),
            top_services_text="风险服务: " + service.name,
            todo_text=f"待处理Issue: {summary['open_issues']}，待合并PR: {summary['open_prs']}"
        )

        result = send_template_card("periodic_digest", variables)
        if result:
            append_audit_event("digest_card_sent", "system", {"card_type": "periodic_digest"})
            mock_tag = " (模拟)" if result.get("mock") else ""
            return TriggerResponse(
                success=True,
                message=f"统计摘要卡片已发送{mock_tag}",
                data={"stats": summary}
            )
        else:
            return TriggerResponse(
                success=False,
                message="统计摘要卡片发送失败"
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

def run_server(host: str = "127.0.0.1", port: int = 8888):
    """启动Dashboard服务器"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_server()
