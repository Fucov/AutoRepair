from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import time

from autorepair.incident_store import load_incidents
from autorepair.repair.job_store import load_repair_jobs
from autorepair.adapters.github import _load_mock_issues, _load_mock_prs


# 简单内存缓存：缓存统计结果，5 秒内重复请求直接返回缓存
_stats_cache: Dict[str, Dict[str, Any]] = {}
_STATS_CACHE_TTL = 5  # 缓存过期时间（秒）


def _get_cached(key: str, factory) -> Dict[str, Any]:
    """带 TTL 的简单缓存"""
    now = time.monotonic()
    cached = _stats_cache.get(key)
    if cached and now - cached["_ts"] < _STATS_CACHE_TTL:
        return cached["data"]
    data = factory()
    _stats_cache[key] = {"_ts": now, "data": data}
    return data


def get_system_stats() -> Dict[str, Any]:
    """获取系统整体统计数据（带缓存）"""
    def _build():
        incidents = list(load_incidents())
        jobs = list(load_repair_jobs())
        issues = _load_mock_issues()
        prs = _load_mock_prs()

        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 统计Incident数据
        total_incidents = len(incidents)
        today_incidents = 0
        error_type_dist: Dict[str, int] = defaultdict(int)
        service_dist: Dict[str, int] = defaultdict(int)

        for inc in incidents:
            inc_time = datetime.fromisoformat(inc.created_at.replace("Z", "+00:00")).replace(tzinfo=None)
            if inc_time >= today:
                today_incidents += 1
            error_type_dist[inc.error_summary.error_type] += 1
            service_dist[inc.service_name or inc.service or "unknown"] += 1

        # 统计修复任务数据
        total_jobs = len(jobs)
        job_status_dist: Dict[str, int] = defaultdict(int)
        successful_repairs = 0
        failed_repairs = 0

        for job in jobs:
            job_status_dist[job.status.value] += 1
            if job.status.value == "pr_created" or job.status.value == "merged":
                successful_repairs += 1
            elif job.status.value == "failed" or job.status.value == "test_failed" or job.status.value == "human_required":
                failed_repairs += 1

        repair_success_rate = successful_repairs / max(total_jobs, 1) * 100

        # 统计Issue和PR数据
        open_issues = sum(1 for issue in issues if issue.get("state") == "open")
        closed_issues = sum(1 for issue in issues if issue.get("state") == "closed")
        open_prs = sum(1 for pr in prs if pr.get("state") == "open")
        merged_prs = sum(1 for pr in prs if pr.get("merged"))

        # 最近24小时趋势
        hourly_incidents = [0] * 24
        for inc in incidents:
            inc_time = datetime.fromisoformat(inc.created_at.replace("Z", "+00:00")).replace(tzinfo=None)
            if inc_time >= now - timedelta(hours=24):
                hour_diff = int((now - inc_time).total_seconds() / 3600)
                if 0 <= hour_diff < 24:
                    hourly_incidents[23 - hour_diff] += 1

        return {
            "summary": {
                "total_incidents": total_incidents,
                "today_incidents": today_incidents,
                "total_repair_jobs": total_jobs,
                "successful_repairs": successful_repairs,
                "failed_repairs": failed_repairs,
                "repair_success_rate": round(repair_success_rate, 2),
                "open_issues": open_issues,
                "closed_issues": closed_issues,
                "open_prs": open_prs,
                "merged_prs": merged_prs,
                "pending_jobs": job_status_dist.get("queued", 0),
                "running_jobs": job_status_dist.get("running", 0)
            },
            "distributions": {
                "error_type": dict(error_type_dist),
                "service": dict(service_dist),
                "job_status": dict(job_status_dist)
            },
            "trends": {
                "last_24h_incidents": hourly_incidents
            },
            "updated_at": now.isoformat()
        }

    return _get_cached("system_stats", _build)


def get_incident_list(limit: int = 100) -> List[Dict[str, Any]]:
    """获取Incident列表"""
    incidents = list(load_incidents())
    incidents.sort(key=lambda x: x.created_at, reverse=True)
    
    result = []
    for inc in incidents[:limit]:
        result.append({
            "incident_id": inc.incident_id,
            "error_type": inc.error_summary.error_type,
            "error_message": inc.error_summary.message,
            "service": inc.service_name or inc.service,
            "suspected_file": inc.error_summary.suspected_file,
            "line_no": inc.error_summary.line_no,
            "occurrence_count": inc.occurrence_count,
            "status": inc.status,
            "issue_number": inc.issue_number,
            "issue_url": inc.issue_url,
            "created_at": inc.created_at,
            "updated_at": inc.updated_at
        })
    return result


def get_repair_job_list(limit: int = 100) -> List[Dict[str, Any]]:
    """获取修复任务列表"""
    jobs = list(load_repair_jobs())
    jobs.sort(key=lambda x: x.created_at, reverse=True)
    
    result = []
    for job in jobs[:limit]:
        result.append({
            "job_id": job.job_id,
            "incident_id": job.incident_id,
            "issue_number": job.issue_number,
            "issue_url": job.issue_url,
            "report_url": job.report_url,
            "service_name": job.service_name,
            "status": job.status.value,
            "repair_branch": job.repair_branch,
            "pr_number": job.pr_number,
            "pr_url": job.pr_url,
            "risk_level": job.risk_level,
            "policy_result": job.policy_result,
            "last_error": job.last_error,
            "created_at": job.created_at,
            "updated_at": job.updated_at
        })
    return result


def get_issue_list(limit: int = 100) -> List[Dict[str, Any]]:
    """获取Issue列表"""
    issues = _load_mock_issues()
    issues.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    result = []
    for issue in issues[:limit]:
        result.append({
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "labels": issue.get("labels", []),
            "html_url": issue.get("html_url"),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at")
        })
    return result


def get_pr_list(limit: int = 100) -> List[Dict[str, Any]]:
    """获取PR列表"""
    prs = _load_mock_prs()
    prs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    result = []
    for pr in prs[:limit]:
        result.append({
            "number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "head": pr.get("head"),
            "base": pr.get("base"),
            "merged": pr.get("merged", False),
            "html_url": pr.get("html_url"),
            "created_at": pr.get("created_at")
        })
    return result
