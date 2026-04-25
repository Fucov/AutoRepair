import os
import httpx
from typing import Optional
from datetime import datetime
from .schemas import Incident, TargetService, DiagnosticReport, DiagnosticCheck


def run_basic_diagnostics(incident: Incident, service: TargetService) -> DiagnosticReport:
    """
    对Incident执行基础诊断，生成诊断报告
    """
    checks = []
    now = datetime.utcnow().isoformat()

    # 1. 服务配置检查
    repo_exists = os.path.exists(service.repo_path)
    log_paths_configured = len(service.log_paths) > 0
    healthcheck_configured = service.healthcheck_url is not None
    
    service_check_passed = repo_exists and log_paths_configured
    checks.append(DiagnosticCheck(
        name="service_config_check",
        status="passed" if service_check_passed else "failed",
        detail=f"repo_path exists: {repo_exists}, log_paths configured: {log_paths_configured}, healthcheck configured: {healthcheck_configured}"
    ))

    # 2. 健康检查
    healthcheck_status = "skipped"
    healthcheck_detail = "no healthcheck_url configured"
    if service.healthcheck_url:
        try:
            response = httpx.get(service.healthcheck_url, timeout=2)
            if response.status_code >= 200 and response.status_code < 300:
                healthcheck_status = "passed"
                healthcheck_detail = f"status code: {response.status_code}"
            else:
                healthcheck_status = "failed"
                healthcheck_detail = f"status code: {response.status_code}"
        except Exception as e:
            healthcheck_status = "failed"
            healthcheck_detail = f"request failed: {str(e)}"
    
    checks.append(DiagnosticCheck(
        name="healthcheck",
        status=healthcheck_status,
        detail=healthcheck_detail
    ))

    # 3. 代码仓库检查
    git_dir_exists = os.path.exists(os.path.join(service.repo_path, ".git"))
    repo_check_passed = repo_exists
    checks.append(DiagnosticCheck(
        name="repo_check",
        status="passed" if repo_check_passed else "failed",
        detail=f"repo_path exists: {repo_exists}, .git directory exists: {git_dir_exists}"
    ))

    # 4. 日志证据检查
    traceback_exists = bool(incident.raw_traceback)
    error_summary_exists = incident.error_summary is not None
    log_check_passed = traceback_exists and error_summary_exists
    checks.append(DiagnosticCheck(
        name="log_evidence_check",
        status="passed" if log_check_passed else "failed",
        detail=f"raw_traceback exists: {traceback_exists}, error_summary exists: {error_summary_exists}"
    ))

    # 5. 测试命令检查
    test_command_configured = service.test_command is not None
    checks.append(DiagnosticCheck(
        name="test_command_check",
        status="passed" if test_command_configured else "skipped",
        detail=f"test_command configured: {test_command_configured}"
    ))

    # 6. 问题分类
    classification = "unknown"
    if incident.error_summary:
        error_type = incident.error_summary.error_type
        if "ModuleNotFoundError" in error_type or "ImportError" in error_type:
            classification = "dependency_missing"
    
    if incident.source == "github_issue" and not incident.raw_traceback:
        classification = "business_logic_bug"
    elif incident.raw_traceback:
        classification = "runtime_exception"

    # 7. 可修复性判断
    fixability = "needs_more_info"
    if classification == "dependency_missing":
        fixability = "human_required"
    elif classification == "runtime_exception" and repo_exists:
        fixability = "auto_fix_candidate"
    elif classification == "business_logic_bug" and service.agent_target_test_command:
        fixability = "auto_fix_candidate"
    elif healthcheck_status == "failed" and not traceback_exists:
        fixability = "human_required"

    return DiagnosticReport(
        incident_id=incident.incident_id,
        service_id=service.service_id,
        checks=checks,
        classification=classification,
        fixability=fixability,
        created_at=now
    )
