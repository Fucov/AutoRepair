from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import uvicorn
from pathlib import Path
import sys
import os
import asyncio
import logging
import threading
from collections import deque

logger = logging.getLogger(__name__)

from autorepair.dashboard.stats import (
    get_system_stats,
    get_incident_list,
    get_repair_job_list,
    get_issue_list,
    get_pr_list,
)
from autorepair.watcher import scan_service_logs_once
from autorepair.service_registry import get_default_service
from autorepair.adapters import feishu
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
from autorepair.repair.job_store import create_repair_job
from autorepair.repair.job_store import DEFAULT_REPAIR_JOBS_PATH
from autorepair.repair.git_workspace import build_repair_branch
from autorepair.repair.schemas import RepairJobStatus
from autorepair.config import config, LOG_PATH, GITHUB_OWNER, GITHUB_REPO
from autorepair.dashboard.watchdog import start_watchdog, stop_watchdog, get_watchdog_status
from autorepair.scheduler import issue_poller


@asynccontextmanager
async def lifespan(app_instance):
    try:
        start_watchdog()
        logger.info("watchdog 已随 Dashboard 启动")
    except Exception as e:
        logger.error(f"watchdog 启动失败: {e}", exc_info=True)
    try:
        issue_poller.start()
        logger.info("IssuePoller 已随 Dashboard 启动")
    except Exception as e:
        logger.error(f"IssuePoller 启动失败: {e}", exc_info=True)
    yield
    try:
        issue_poller.stop()
    except Exception as e:
        logger.error(f"IssuePoller 停止失败: {e}", exc_info=True)
    try:
        stop_watchdog()
    except Exception as e:
        logger.error(f"watchdog 停止失败: {e}", exc_info=True)


app = FastAPI(title="FeishuAutoRepair Dashboard", version="2.0.0", lifespan=lifespan)

EVENT_QUEUE: deque = deque(maxlen=200)
EVENT_WAITERS: list[asyncio.Future] = []
LAST_EVENT_ID = 0
_event_loop: asyncio.AbstractEventLoop | None = None


def push_event(event_type: str, data: dict = None):
    global LAST_EVENT_ID
    LAST_EVENT_ID += 1
    event = {
        "id": LAST_EVENT_ID,
        "type": event_type,
        "data": data or {},
        "timestamp": datetime.now().isoformat(),
    }
    EVENT_QUEUE.append(event)

    if not EVENT_WAITERS:
        return

    try:
        loop = EVENT_WAITERS[0].get_loop()
        if loop.is_running():
            if threading.current_thread() is not threading.main_thread():
                loop.call_soon_threadsafe(_resolve_waiters, event)
            else:
                _resolve_waiters(event)
    except (IndexError, RuntimeError):
        pass


def _resolve_waiters(event: dict):
    for future in EVENT_WAITERS:
        if not future.done():
            future.set_result(event)
    EVENT_WAITERS.clear()


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "FeishuAutoRepair Dashboard API"}


@app.get("/api/stats")
async def api_get_stats() -> Dict[str, Any]:
    return get_system_stats()


@app.get("/api/incidents")
async def api_get_incidents(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    return get_incident_list(limit=limit)


@app.get("/api/issues")
async def api_get_issues(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    return get_issue_list(limit=limit)


@app.get("/api/repair_jobs")
async def api_get_repair_jobs(limit: Optional[int] = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    jobs = get_repair_job_list(limit=limit)
    if status:
        jobs = [job for job in jobs if job["status"] == status]
    return jobs


@app.get("/api/prs")
async def api_get_prs(limit: Optional[int] = 100) -> List[Dict[str, Any]]:
    return get_pr_list(limit=limit)


class TriggerResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


@app.post("/api/trigger/scan_logs", response_model=TriggerResponse)
async def api_trigger_scan_logs():
    try:
        service = get_default_service()
        results = scan_service_logs_once(service)
        if not results:
            return TriggerResponse(
                success=True,
                message="日志扫描完成，未发现新异常",
                data={"incidents_created": 0, "incidents_updated": 0, "issues_created": 0, "cards_sent": 0},
            )

        created_count = 0
        updated_count = 0
        feishu_sent_count = 0
        issue_created_count = 0
        details = []

        for incident, action in results:
            summary = incident.error_summary
            if action == "created":
                created_count += 1
                issue_ref = ensure_issue_for_incident(incident, service)
                issue_url = issue_ref.html_url
                incident.issue_number = issue_ref.number
                incident.issue_url = issue_url
                update_incident_fields(incident.incident_id, issue_number=issue_ref.number, issue_url=issue_url)
                if issue_url:
                    issue_created_count += 1
                    details.append(f"Created Issue: {issue_url}")
                send_result = send_incident_card(incident)
                if send_result:
                    feishu_sent_count += 1
                    append_audit_event(
                        "feishu_card_sent" if not send_result.get("mock") else "feishu_card_mocked",
                        incident.incident_id,
                        {"card_type": "incident_detected"},
                    )
                else:
                    append_audit_event("feishu_card_failed", incident.incident_id, {"card_type": "incident_detected"})
                append_audit_event("incident_created", incident.incident_id, {
                    "error_type": summary.error_type,
                    "service": incident.service,
                    "issue_url": issue_url,
                })
                details.append(f"[created] {incident.incident_id} {summary.error_type} {incident.service_name} occurrence_count={incident.occurrence_count}")
            else:
                updated_count += 1
                details.append(f"[updated] {incident.incident_id} occurrence_count={incident.occurrence_count}")

        response = TriggerResponse(
            success=True,
            message=f"日志扫描完成：创建{created_count}个Incident，更新{updated_count}个，创建{issue_created_count}个Issue，发送{feishu_sent_count}个飞书卡片",
            data={
                "incidents_created": created_count,
                "incidents_updated": updated_count,
                "issues_created": issue_created_count,
                "cards_sent": feishu_sent_count,
                "service": service.name,
                "details": details,
            },
        )
        push_event("logs_scanned", {
            "incidents_created": created_count,
            "incidents_updated": updated_count,
            "issues_created": issue_created_count,
            "cards_sent": feishu_sent_count,
        })
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"日志扫描失败: {str(e)}")


@app.post("/api/trigger/scan_issues", response_model=TriggerResponse)
async def api_trigger_scan_issues():
    try:
        service = get_default_service()
        issues = list_open_bug_issues()

        if not issues:
            return TriggerResponse(
                success=True,
                message="Issue扫描完成，未发现待处理的Bug Issue",
                data={"issues_found": 0, "suitable_for_fix": 0, "manual_intervention": 0},
            )

        suitable_count = 0
        manual_count = 0
        details = []

        for issue in issues:
            issue_id = f"ISSUE-{issue.number}"
            labels = issue.labels
            if "bug" not in labels or "AutoRepair" not in labels:
                details.append(f"#{issue.number}: 缺少必要标签，跳过")
                continue
            if any(tag in labels for tag in ["invalid", "wontfix", "question"]):
                details.append(f"#{issue.number}: 标记为无需处理，跳过")
                continue

            keywords = ["TypeError", "AttributeError", "IndexError", "KeyError", "ZeroDivisionError"]
            has_error_keyword = any(kw.lower() in issue.title.lower() for kw in keywords)
            has_traceback = "Traceback" in issue.body or 'File "' in issue.body

            if has_error_keyword or has_traceback:
                suitable_count += 1
                import uuid
                repair_branch = f"autorepair/issue-{issue.number}-{uuid.uuid4().hex[:6]}"
                repair_job = create_repair_job(
                    incident_id=issue_id,
                    issue_number=issue.number,
                    service_name=service.name,
                    repo_owner=config.GITHUB_OWNER or "default-owner",
                    repo_name=config.GITHUB_REPO or "default-repo",
                    base_branch="main",
                    repair_branch=repair_branch,
                    worktree_path=f"/tmp/worktree/{repair_branch}",
                    policy_decision={"decision": "auto_fix", "confidence": "high"},
                    risk_level="low",
                )
                variables = build_repair_plan_ready_variables(
                    incident_id=issue_id,
                    service_name=service.name,
                    root_cause="系统检测到可自动修复的代码错误",
                    fix_strategy="分析Traceback并生成修复补丁",
                    risk_level="低风险",
                    policy_summary="允许进入自动修复",
                )
                send_template_card("repair_plan_ready", variables)
                append_audit_event("repair_plan_generated", issue_id, {
                    "issue_number": issue.number,
                    "issue_url": issue.html_url,
                    "job_id": repair_job.job_id,
                })
                append_audit_event("repair_job_created", issue_id, {
                    "job_id": repair_job.job_id,
                    "issue_number": issue.number,
                })
                details.append(f"#{issue.number}: 适合自动修复，已创建修复任务 {repair_job.job_id} 并发送通知卡片")
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
                    "issue_url": issue.html_url,
                })
                details.append(f"#{issue.number}: 需要人工介入，已发送通知卡片")

        response = TriggerResponse(
            success=True,
            message=f"Issue扫描完成：发现{len(issues)}个Issue，{suitable_count}个适合修复，{manual_count}个需要人工介入",
            data={"issues_found": len(issues), "suitable_for_fix": suitable_count, "manual_intervention": manual_count, "details": details},
        )
        push_event("issues_scanned", {"issues_found": len(issues), "suitable_for_fix": suitable_count, "jobs_created": suitable_count})
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Issue扫描失败: {str(e)}")


@app.post("/api/trigger/run_repair", response_model=TriggerResponse)
async def api_trigger_run_repair():
    try:
        from autorepair.repair.executor import execute_next_repair_job
        result = execute_next_repair_job()

        if result.error:
            push_event("repair_executed", {
                "job_id": result.job.job_id if result.job else None,
                "success": False,
                "error": result.error,
                "failure_type": result.failure_type,
            })
            return TriggerResponse(
                success=True,
                message=result.error,
                data={"job_id": result.job.job_id if result.job else None, "failure_type": result.failure_type},
            )

        if result.job:
            push_event("repair_executed", {
                "job_id": result.job.job_id,
                "status": result.job.status.value,
                "pr_url": result.job.pr_url,
                "success": True,
            })
            return TriggerResponse(
                success=True,
                message=f"修复任务完成: {result.job.job_id}",
                data={"job_id": result.job.job_id, "status": result.job.status.value, "pr_url": result.job.pr_url, "pr_number": result.job.pr_number},
            )

        push_event("repair_executed", {"success": True, "message": "没有待执行的修复任务"})
        return TriggerResponse(success=True, message="没有待执行的修复任务", data={"jobs_created": 0})
    except Exception as e:
        push_event("repair_executed", {"success": False, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"修复任务执行失败: {str(e)}")


@app.post("/api/trigger/run_all_repairs", response_model=TriggerResponse)
async def api_trigger_run_all_repairs(max_concurrent: int = 3):
    try:
        from autorepair.repair.executor import process_all_queued_jobs
        results = await process_all_queued_jobs(max_concurrent=max_concurrent)

        success_count = sum(1 for r in results if r.success)
        total_count = len(results)

        push_event("all_repairs_executed", {
            "total_jobs": total_count,
            "success_count": success_count,
            "failed_count": total_count - success_count,
        })

        return TriggerResponse(
            success=True,
            message=f"批量修复任务完成：总任务数{total_count}，成功{success_count}，失败{total_count - success_count}",
            data={"total_jobs": total_count, "success_count": success_count, "failed_count": total_count - success_count},
        )
    except Exception as e:
        push_event("all_repairs_executed", {"success": False, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"批量修复任务执行失败: {str(e)}")


@app.post("/api/trigger/sync_prs", response_model=TriggerResponse)
async def api_trigger_sync_prs():
    try:
        from autorepair.repair.job_store import DEFAULT_REPAIR_JOBS_PATH, load_repair_jobs
        from autorepair.repair.schemas import RepairJobStatus

        jobs = [job for job in load_repair_jobs(DEFAULT_REPAIR_JOBS_PATH) if job.status == RepairJobStatus.pr_created]
        if not jobs:
            return TriggerResponse(success=True, message="没有需要同步的PR状态", data={"updated_jobs": 0})

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

        push_event("prs_synced", {"merged": merged_count, "closed_without_merge": closed_count})
        return TriggerResponse(
            success=True,
            message=f"PR状态同步完成：合并{merged_count}个，关闭{closed_count}个",
            data={"merged": merged_count, "closed_without_merge": closed_count},
        )
    except Exception as e:
        push_event("prs_synced", {"success": False, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"PR状态同步失败: {str(e)}")


@app.post("/api/trigger/send_digest", response_model=TriggerResponse)
async def api_trigger_send_digest():
    try:
        from autorepair.cards import send_periodic_digest
        send_periodic_digest()
        push_event("digest_sent")
        return TriggerResponse(success=True, message="统计摘要已发送")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")


async def _run_full_pipeline_background():
    try:
        service = get_default_service()
        pipeline_details: list[str] = []

        push_event("pipeline_started", {"message": "全流程开始执行"})
        await asyncio.sleep(0)

        results = scan_service_logs_once(service)
        if not results:
            push_event("pipeline_completed", {"message": "全流程完成：未发现新异常"})
            return

        pipeline_details.append(f"扫描到 {len(results)} 个日志事件")

        for incident, action in results:
            if action != "created":
                continue

            push_event("incident_detected", {
                "incident_id": incident.incident_id,
                "error_type": incident.error_summary.error_type,
                "message": f"检测到异常: {incident.error_summary.error_type}",
            })
            await asyncio.sleep(0)

            issue_ref = ensure_issue_for_incident(incident, service)
            issue_url = issue_ref.html_url
            incident.issue_number = issue_ref.number
            incident.issue_url = issue_url
            update_incident_fields(incident.incident_id, issue_number=issue_ref.number, issue_url=issue_url)
            pipeline_details.append(f"创建Issue: {issue_url}")

            push_event("issue_created", {
                "incident_id": incident.incident_id,
                "issue_number": issue_ref.number,
                "issue_url": issue_ref.html_url,
                "message": f"Issue已创建: #{issue_ref.number}",
            })
            await asyncio.sleep(0)

            try:
                from autorepair.reports.diagnostic_report_builder import build_diagnostic_report
                from autorepair.adapters.note_report import NoteReportClient

                note_client = NoteReportClient()
                triage_result = type("MockTriageResult", (), {
                    "root_cause": f"{incident.error_summary.error_type}: {incident.error_summary.message}",
                    "risk_level": "medium",
                })()
                report = build_diagnostic_report(
                    issue=issue_ref if hasattr(issue_ref, "title") else type("MockIssue", (), {
                        "title": f"Bug: {incident.error_summary.error_type}",
                        "body": incident.raw_traceback[:500],
                        "labels": ["bug", "AutoRepair"],
                        "number": issue_ref.number,
                        "html_url": issue_ref.html_url,
                    })(),
                    incident=incident,
                    validation_result="通过",
                    triage_result=triage_result,
                    policy_result="allowed",
                )
                doc_ref = note_client.create_diagnostic_report(report)

                push_event("diagnostic_report_created", {
                    "incident_id": incident.incident_id,
                    "issue_number": issue_ref.number,
                    "report_url": doc_ref.url,
                    "message": "诊断报告生成完成",
                })
                pipeline_details.append(f"诊断报告: {doc_ref.url}")
                await asyncio.sleep(0)
            except Exception as e:
                logger.error(f"生成诊断报告失败: {e}", exc_info=True)
                doc_ref = None

            plan_ref = None
            try:
                from autorepair.reports.repair_plan_builder import build_repair_plan, render_repair_plan_plaintext

                plan = build_repair_plan(
                    incident=incident,
                    service_name=service.name,
                    test_command=service.agent_target_test_command or service.test_command,
                )
                plan_content = render_repair_plan_plaintext(plan)
                plan_title = f"修复计划 - {incident.incident_id} - {incident.error_summary.error_type}"
                plan_ref = note_client.create_report(plan_title, plan_content)
                push_event("repair_plan_created", {
                    "incident_id": incident.incident_id,
                    "issue_number": issue_ref.number,
                    "plan_url": plan_ref.url,
                    "message": "修复计划文档生成完成",
                })
                pipeline_details.append(f"修复计划: {plan_ref.url}")
                await asyncio.sleep(0)
            except Exception as e:
                logger.error(f"生成修复计划失败: {e}", exc_info=True)

            plan_url = plan_ref.url if plan_ref else (doc_ref.url if doc_ref else "")
            send_result = send_incident_card(incident)
            feishu.send_repair_plan_ready(
                incident_id=incident.incident_id,
                service_name=service.name,
                diagnosis_brief=f"{incident.error_summary.error_type}: {incident.error_summary.message}",
                fix_strategy="自动分析Traceback并生成修复补丁",
                risk_level="medium",
                policy_result="allowed",
                report_url=plan_url,
            )

            push_event("card_sent", {
                "incident_id": incident.incident_id,
                "issue_number": issue_ref.number,
                "message": "飞书卡片已发送",
            })
            pipeline_details.append("飞书卡片已发送")
            await asyncio.sleep(0)

            repair_branch = build_repair_branch(incident.incident_id, incident.error_summary.error_type)
            worktree_path = str(Path(service.repo_path) / ".worktrees" / incident.incident_id)
            job = create_repair_job(
                incident_id=incident.incident_id,
                issue_number=issue_ref.number,
                issue_url=issue_ref.html_url,
                service_name=service.name,
                repo_owner=GITHUB_OWNER or "local",
                repo_name=GITHUB_REPO or Path(service.repo_path).name,
                base_branch=os.getenv("GITHUB_BASE_BRANCH", "main"),
                repair_branch=repair_branch,
                worktree_path=worktree_path,
                policy_decision={"decision": "auto_fix", "confidence": "high"},
                risk_level="medium",
                report_url=plan_url,
                path=DEFAULT_REPAIR_JOBS_PATH,
            )

            push_event("repair_job_created", {
                "job_id": job.job_id,
                "incident_id": incident.incident_id,
                "issue_number": issue_ref.number,
                "report_url": doc_ref.url if doc_ref else "",
                "message": "修复任务已加入队列",
            })
            pipeline_details.append(f"修复任务: {job.job_id}")
            await asyncio.sleep(0)

            append_audit_event("pipeline_incident_processed", incident.incident_id, {
                "issue_number": issue_ref.number,
                "report_url": doc_ref.url if doc_ref else "",
                "job_id": job.job_id,
            })

        from autorepair.repair.executor import execute_next_repair_job
        from autorepair.repair.job_store import load_repair_jobs
        from autorepair.repair.schemas import RepairJobStatus

        for _ in range(5):
            queued = [j for j in load_repair_jobs() if j.status == RepairJobStatus.queued]
            if not queued:
                break
            repair_result = execute_next_repair_job()
            if repair_result.job:
                pipeline_details.append(f"修复执行 [{repair_result.job.job_id}]: {repair_result.job.status.value}")
                if repair_result.job.pr_url:
                    pipeline_details.append(f"PR: {repair_result.job.pr_url}")
            if not repair_result.success and not repair_result.job:
                break

        push_event("pipeline_completed", {
            "message": "全流程执行完成",
            "details": pipeline_details,
        })
    except Exception as e:
        logger.error(f"全流程执行失败: {e}", exc_info=True)
        push_event("pipeline_failed", {"message": f"全流程执行失败: {str(e)}"})


@app.post("/api/trigger/run_full_pipeline", response_model=TriggerResponse)
async def api_trigger_full_pipeline():
    asyncio.create_task(_run_full_pipeline_background())
    push_event("pipeline_started", {"message": "全流程已启动，请关注事件流"})
    return TriggerResponse(
        success=True,
        message="全流程已启动，请关注事件流",
        data={"status": "started"},
    )


@app.get("/api/watchdog/status")
async def api_watchdog_status():
    return get_watchdog_status()


@app.post("/api/watchdog/start", response_model=TriggerResponse)
async def api_watchdog_start():
    try:
        start_watchdog()
        return TriggerResponse(success=True, message="文件监控已启动")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动监控失败: {str(e)}")


@app.post("/api/watchdog/stop", response_model=TriggerResponse)
async def api_watchdog_stop():
    try:
        stop_watchdog()
        return TriggerResponse(success=True, message="文件监控已停止")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止监控失败: {str(e)}")


@app.get("/api/poller/status")
async def api_poller_status():
    return issue_poller.get_status()


@app.post("/api/poller/start", response_model=TriggerResponse)
async def api_poller_start():
    try:
        issue_poller.start()
        return TriggerResponse(success=True, message="Issue轮询已启动")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动Issue轮询失败: {str(e)}")


@app.post("/api/poller/stop", response_model=TriggerResponse)
async def api_poller_stop():
    try:
        issue_poller.stop()
        return TriggerResponse(success=True, message="Issue轮询已停止")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止Issue轮询失败: {str(e)}")


@app.get("/api/events/long-poll")
async def long_poll_events(last_event_id: int = 0):
    if EVENT_QUEUE and EVENT_QUEUE[-1]["id"] > last_event_id:
        new_events = [e for e in EVENT_QUEUE if e["id"] > last_event_id]
        return {"events": new_events, "last_event_id": EVENT_QUEUE[-1]["id"]}

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    EVENT_WAITERS.append(future)

    try:
        await asyncio.wait_for(future, timeout=30)
        new_events = [e for e in EVENT_QUEUE if e["id"] > last_event_id]
        return {"events": new_events, "last_event_id": new_events[-1]["id"] if new_events else last_event_id}
    except asyncio.TimeoutError:
        new_events = [e for e in EVENT_QUEUE if e["id"] > last_event_id]
        return {"events": new_events, "last_event_id": new_events[-1]["id"] if new_events else last_event_id}
    finally:
        if future in EVENT_WAITERS:
            EVENT_WAITERS.remove(future)


@app.get("/api/config")
async def api_get_config() -> Dict[str, Any]:
    return {
        "FEISHU_API_BASE_URL": config.FEISHU_API_BASE_URL,
        "FEISHU_APP_ID": config.FEISHU_APP_ID,
        "FEISHU_CHAT_ID": config.FEISHU_CHAT_ID,
        "GITHUB_API_BASE_URL": config.GITHUB_API_BASE_URL,
        "GITHUB_OWNER": config.GITHUB_OWNER,
        "GITHUB_REPO": config.GITHUB_REPO,
        "GITHUB_ASSIGNEE": config.GITHUB_ASSIGNEE,
        "TEST_CMD": config.TEST_CMD,
        "LOG_PATH": str(LOG_PATH),
    }


class ConfigUpdate(BaseModel):
    key: str
    value: Any


@app.post("/api/config", response_model=TriggerResponse)
async def api_update_config(update: ConfigUpdate):
    try:
        return TriggerResponse(success=True, message="配置更新功能待实现")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")


def run_server(host: str = "127.0.0.1", port: int = 8888):
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
