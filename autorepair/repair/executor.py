from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Set
from pydantic import BaseModel
from autorepair.adapters.llm_client import LLMClient
from autorepair.repair_agent.context import build_repair_agent_context
from autorepair.repair_agent.history_context import collect_history_context
from autorepair.repair_agent.loop import MiniRepairAgent
from autorepair.repair_agent.playbooks import try_apply_known_playbook, try_apply_skill_backed_playbook
from autorepair.repair_agent.repair_case import build_repair_case
from autorepair.repair_agent.schemas import RepairAgentResult
from autorepair.repair_agent.spec_builder import build_repair_spec
from autorepair.repair_agent.skills import select_repair_skills
from autorepair.repair_agent.tools import MiniRepairTools
from autorepair.repair_agent.validator import build_validation_plan
from autorepair.adapters.github import (
    find_open_pr_for_branch,
    create_pull_request,
    comment_issue,
    replace_autorepair_status_label,
)
from autorepair.adapters.feishu import send_manual_intervention_card, send_fix_pr_ready_card
from autorepair.audit_store import append_audit_event
from autorepair.dashboard.api import push_event
from autorepair.incident_store import get_incident_by_id
from autorepair.service_registry import get_default_service
from autorepair.repair.context_collector import collect_repair_context
from autorepair.repair.git_workspace import (
    create_repair_worktree,
    git_commit_all,
    git_push_branch,
    get_git_diff,
    remove_repair_worktree,
)
from autorepair.repair.job_store import (
    find_oldest_queued_job,
    update_repair_job,
    find_jobs_by_incident_id,
    find_jobs_by_issue_number,
    load_repair_jobs,
)
from autorepair.repair.repo_lock import acquire_repo_lock
from autorepair.repair.schemas import RepairJobStatus, RepairJob

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

FAILURE_REASON_MAP = {
    "context_failed": "无法从 traceback 中解析出错误文件路径，请检查日志格式",
    "patch_apply_failed": "LLM 返回的旧代码在文件中找不到匹配，可能文件已被修改",
    "target_test_failed": "目标测试失败，修复可能不完整",
    "full_test_failed": "回归测试未通过，修复可能引入了新问题",
    "llm_error": "LLM 服务不可用，请检查 API 配置",
    "pr_create_failed": "代码修复成功但 PR 创建失败，请手动创建 PR",
    "unknown": "发生未知错误",
}


def _classify_failure(error_msg: str) -> str:
    lower = error_msg.lower()
    if "patch apply" in lower or "old content" in lower or "未找到 old" in lower or "模糊匹配" in lower:
        return "patch_apply_failed"
    if "target test" in lower or "target_test" in lower:
        return "target_test_failed"
    if "full test" in lower or "full_test" in lower or "regression" in lower:
        return "full_test_failed"
    if "llm" in lower or "api" in lower or "timeout" in lower or "connection" in lower:
        return "llm_error"
    if "pull request" in lower or "pr" in lower:
        return "pr_create_failed"
    if "context" in lower or "traceback" in lower:
        return "context_failed"
    return "unknown"


def _build_failure_report(failure_type: str, error_msg: str, attempt: int) -> str:
    reason = FAILURE_REASON_MAP.get(failure_type, FAILURE_REASON_MAP["unknown"])
    report = f"【失败类型】{failure_type}\n"
    report += f"【失败原因】{reason}\n"
    report += f"【第{attempt}次尝试】\n"
    report += f"【详细错误】{error_msg[:1000]}\n"
    if failure_type == "patch_apply_failed":
        report += "【建议】请确保 old 内容是文件中实际存在的连续完整文本，包括正确的缩进"
    elif failure_type == "target_test_failed":
        report += "【建议】请分析测试输出，理解期望行为，调整修复策略"
    elif failure_type == "full_test_failed":
        report += "【建议】修复引入了新问题，请缩小修改范围"
    elif failure_type == "llm_error":
        report += "【建议】请检查 LLM API 配置是否正确，服务是否可用"
    return report


class RepairExecutionResult(BaseModel):
    success: bool
    job: RepairJob | None = None
    error: str | None = None
    failure_type: str | None = None
    failure_report: str | None = None


def _has_active_job_for_issue(issue_number: int) -> bool:
    jobs = find_jobs_by_issue_number(issue_number)
    for job in jobs:
        if job.status in {RepairJobStatus.running, RepairJobStatus.pr_created}:
            return True
    return False


def _has_open_pr_for_branch(branch: str) -> bool:
    return find_open_pr_for_branch(branch) is not None


def execute_next_repair_job() -> RepairExecutionResult:
    job = find_oldest_queued_job()
    if not job:
        return RepairExecutionResult(success=True, error="No queued repair job")

    if _has_active_job_for_issue(job.issue_number):
        return RepairExecutionResult(
            success=True,
            error=f"Active job or open PR already exists for issue #{job.issue_number}",
        )

    repo_key = f"{job.repo_owner}/{job.repo_name}"
    with acquire_repo_lock(repo_key) as lock:
        if not lock.acquired:
            return RepairExecutionResult(
                success=True,
                error=f"Repo lock busy for {repo_key}; job remains queued",
            )

        try:
            update_repair_job(job.job_id, status=RepairJobStatus.running)
            replace_autorepair_status_label(job.issue_number, "autorepair:repairing")

            push_event("repair_started", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "issue_number": job.issue_number,
                "message": f"修复任务 {job.job_id} 开始执行",
            })

            incident = get_incident_by_id(job.incident_id)
            if not incident:
                raise ValueError(f"Incident {job.incident_id} not found")

            service = get_default_service()
            create_repair_worktree(
                repo_path=service.repo_path,
                base_branch=job.base_branch,
                repair_branch=job.repair_branch,
                incident_id=job.incident_id,
            )

            try:
                context = collect_repair_context(job, incident, job.worktree_path)
            except Exception as e:
                failure_type = "context_failed"
                failure_report = _build_failure_report(failure_type, str(e), 0)
                _handle_failure(job, failure_type, failure_report, str(e))
                return RepairExecutionResult(
                    success=False, job=job, error=str(e),
                    failure_type=failure_type, failure_report=failure_report,
                )

            append_audit_event(
                "repair_context_collected",
                job.incident_id,
                {"job_id": job.job_id, "snippets": list(context.code_snippets.keys())},
            )

            push_event("repair_context_collected", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "snippets": list(context.code_snippets.keys()),
                "all_traceback_files": context.all_traceback_files,
                "target_test": context.target_test_command,
                "message": "修复上下文收集完成",
            })

            if not context.code_snippets:
                failure_type = "context_failed"
                failure_report = _build_failure_report(
                    failure_type,
                    "未能从 traceback 中定位到任何项目代码文件，无法生成修复方案",
                    0,
                )
                _handle_failure(job, failure_type, failure_report, failure_report)
                return RepairExecutionResult(
                    success=False, job=job, error=failure_report,
                    failure_type=failure_type, failure_report=failure_report,
                )

            agent_context = build_repair_agent_context(job, incident, service=service)
            if context.target_test_command:
                agent_context = agent_context.model_copy(update={
                    "target_test_command": context.target_test_command,
                    "full_test_command": context.full_test_command,
                })
            repair_case = build_repair_case(agent_context)
            agent_tools = MiniRepairTools(
                job.worktree_path,
                allowed_files=set(repair_case.allowed_files),
                forbidden_files=set(repair_case.forbidden_files),
            )
            repair_spec = build_repair_spec(repair_case, agent_context)
            selected_skills = select_repair_skills(repair_case, repair_spec)
            validation_plan = build_validation_plan(repair_case, repair_spec, agent_context)
            if validation_plan.target_commands:
                agent_context = agent_context.model_copy(update={
                    "target_test_command": validation_plan.target_commands[0],
                })
            history_context = collect_history_context(
                job.worktree_path,
                repair_case.allowed_files,
                line_no=agent_context.line_no,
            )

            append_audit_event("spec_guided_context_built", job.incident_id, {
                "job_id": job.job_id,
                "case_id": repair_case.case_id,
                "scenario_id": repair_case.scenario_id,
                "spec_function": repair_spec.function_under_repair,
                "skills": [s.name for s in selected_skills],
                "target_tests": validation_plan.target_commands,
                "confidence": repair_case.confidence,
            })

            skill_playbook_result = try_apply_skill_backed_playbook(
                agent_context, agent_tools,
                repair_case, repair_spec,
                selected_skills, validation_plan,
            )
            agent_result = skill_playbook_result

            if agent_result is None:
                playbook_result = try_apply_known_playbook(agent_context, agent_tools)
                agent_result = playbook_result

            if agent_result is None:
                agent = MiniRepairAgent(llm_client=LLMClient())
                agent_result = agent.run_spec_guided(
                    agent_context,
                    repair_case=repair_case,
                    repair_spec=repair_spec,
                    skills=selected_skills,
                    validation_plan=validation_plan,
                    history_context=history_context,
                )

            append_audit_event(
                "agent_repair_completed",
                job.incident_id,
                {
                    "job_id": job.job_id,
                    "status": agent_result.status,
                    "summary": agent_result.summary,
                },
            )

            push_event("agent_repair_completed", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "status": agent_result.status,
                "summary": agent_result.summary,
                "message": f"Agent 修复完成: {agent_result.status}",
            })

            update_repair_job(
                job.job_id,
                case_id=repair_case.case_id,
                selected_skills=[s.name for s in selected_skills],
                spec_id=repair_spec.spec_id,
                validation_summary=f"target={agent_result.target_test_passed}, full={agent_result.full_test_passed}",
            )

            if agent_result.status == "fixed":
                diff = agent_result.diff or get_git_diff(job.worktree_path)
                if not diff or not diff.strip():
                    diff = get_git_diff(job.worktree_path)

                commit_message = f"fix: {agent_result.summary[:80]}\n\nIncident: {job.incident_id}\nIssue: #{job.issue_number}"
                commit_sha = git_commit_all(job.worktree_path, commit_message)
                append_audit_event("code_committed", job.incident_id, {"job_id": job.job_id, "commit_sha": commit_sha})
                push_event("code_committed", {"job_id": job.job_id, "incident_id": job.incident_id, "commit_sha": commit_sha, "message": "代码已提交到修复分支"})

                git_push_branch(job.worktree_path, job.repair_branch)
                append_audit_event("branch_pushed", job.incident_id, {"job_id": job.job_id, "branch": job.repair_branch})
                push_event("branch_pushed", {"job_id": job.job_id, "incident_id": job.incident_id, "branch": job.repair_branch, "message": "修复分支已推送到远程"})

                pr_title = f"[AutoRepair] {agent_result.summary[:60]}"
                pr_body = f"""## AutoRepair Fix
Incident ID: {job.incident_id}
Related Issue: #{job.issue_number}

### Root Cause
{context.error_type}: {context.error_message}

### Fix Summary
{agent_result.summary}

### Diff
```diff
{(diff or '')[:3000]}
```
"""
                pr = create_pull_request(pr_title, pr_body, job.repair_branch, job.base_branch)
                if not pr:
                    failure_type = "pr_create_failed"
                    error_detail = "Failed to create pull request"
                    failure_report = _build_failure_report(failure_type, error_detail, MAX_RETRIES)
                    update_repair_job(job.job_id, status=RepairJobStatus.human_required, last_error=error_detail)
                    push_event("repair_failed", {"job_id": job.job_id, "incident_id": job.incident_id, "issue_number": job.issue_number, "error": error_detail, "failure_type": failure_type, "message": f"修复失败: {FAILURE_REASON_MAP[failure_type]}"})
                    return RepairExecutionResult(success=False, job=job, error=error_detail, failure_type=failure_type, failure_report=failure_report)

                update_repair_job(
                    job.job_id,
                    status=RepairJobStatus.pr_created,
                    pr_number=pr.number,
                    pr_url=pr.html_url,
                    last_error=None,
                )

                push_event("pr_created", {
                    "job_id": job.job_id,
                    "incident_id": job.incident_id,
                    "issue_number": job.issue_number,
                    "pr_number": pr.number,
                    "pr_url": pr.html_url,
                    "message": f"PR #{pr.number} 创建成功",
                })

                replace_autorepair_status_label(job.issue_number, "autorepair:pr-ready")

                comment_body = f"""✅ AutoRepair 已生成修复PR：[#{pr.number}]({pr.html_url})
修复摘要：{agent_result.summary}
测试已通过，请人工Review。
"""
                comment_issue(job.issue_number, comment_body)

                send_fix_pr_ready_card(
                    incident_id=job.incident_id,
                    issue_number=job.issue_number,
                    pr_url=pr.html_url,
                    pr_title=pr_title,
                    fix_summary=agent_result.summary,
                    risk_level="low",
                )

                push_event("card_sent", {
                    "job_id": job.job_id,
                    "incident_id": job.incident_id,
                    "card_type": "fix_pr_ready",
                    "message": "PR修复完成卡片已发送到飞书",
                })

                append_audit_event(
                    "pr_created",
                    job.incident_id,
                    {
                        "job_id": job.job_id,
                        "pr_number": pr.number,
                        "pr_url": pr.html_url,
                    },
                )

                push_event("repair_completed", {
                    "job_id": job.job_id,
                    "incident_id": job.incident_id,
                    "issue_number": job.issue_number,
                    "pr_number": pr.number,
                    "pr_url": pr.html_url,
                    "message": f"修复完成！PR #{pr.number} 已创建",
                })

                return RepairExecutionResult(success=True, job=job)

            else:
                failure_type = "target_test_failed" if "test" in agent_result.status else agent_result.status
                error_detail = agent_result.summary
                failure_report = _build_failure_report(failure_type, error_detail, MAX_RETRIES)
                try:
                    report_url = _build_repair_attempt_report(job, failure_type, error_detail, agent_result)
                except Exception:
                    report_url = None
                _handle_failure(job, failure_type, failure_report, error_detail, repair_report_url=report_url)
                return RepairExecutionResult(
                    success=False, job=job, error=error_detail,
                    failure_type=failure_type, failure_report=failure_report,
                )

        except Exception as e:
            error_msg = str(e)
            failure_type = _classify_failure(error_msg)
            failure_report = _build_failure_report(failure_type, error_msg, MAX_RETRIES)
            try:
                report_url = _build_repair_attempt_report(job, failure_type, error_msg)
            except Exception:
                report_url = None
            _handle_failure(job, failure_type, failure_report, error_msg, repair_report_url=report_url)
            try:
                remove_repair_worktree(job.worktree_path)
            except Exception:
                pass
            return RepairExecutionResult(
                success=False, job=job, error=error_msg,
                failure_type=failure_type, failure_report=failure_report,
            )


def _build_repair_attempt_report(
    job: RepairJob,
    failure_type: str,
    error_msg: str,
    agent_result: RepairAgentResult | None = None,
    agent_steps: list | None = None,
) -> str:
    from autorepair.reports.repair_plan_builder import render_repair_plan_plaintext
    from autorepair.reports.schemas import RepairPlanData
    from autorepair.adapters.note_report import NoteReportClient
    import uuid

    plan = RepairPlanData(
        plan_id=f"REPORT-{uuid.uuid4().hex[:8]}",
        incident_id=job.incident_id,
        issue_number=job.issue_number,
        service_name=job.service_name or "unknown",
        error_type=failure_type,
        error_message=error_msg[:300],
        suspected_file=None,
        suspected_line=None,
        suspected_function=None,
        root_cause_analysis=f"修复失败，失败类型: {failure_type}\n失败原因: {FAILURE_REASON_MAP.get(failure_type, error_msg[:200])}",
        fix_steps=_build_fix_steps_text(agent_result, agent_steps),
        affected_files=agent_result.changed_files if agent_result else [],
        test_strategy="修复尝试失败，需要人工介入",
        risk_level="high",
        estimated_changes="未知",
        rollback_plan="直接关闭修复分支即可回退",
    )
    content = render_repair_plan_plaintext(plan)
    title = f"修复尝试报告 - {job.incident_id} - {failure_type}"
    note_client = NoteReportClient()
    ref = note_client.create_report(title, content)
    return ref.url


def _build_fix_steps_text(
    agent_result: RepairAgentResult | None,
    agent_steps: list | None,
) -> list[str]:
    steps = []
    if agent_result:
        steps.append(f"修复结果: {agent_result.status}")
        steps.append(f"修复摘要: {agent_result.summary}")
        if agent_result.target_test_passed:
            steps.append("目标测试: 通过")
        else:
            steps.append("目标测试: 失败")
        if agent_result.full_test_passed:
            steps.append("回归测试: 通过")
        else:
            steps.append("回归测试: 失败")
        if agent_result.diff:
            steps.append(f"代码变更:\n{agent_result.diff[:500]}")
    if agent_steps:
        for step in agent_steps:
            tc = step.tool_call
            tr = step.tool_result
            if tc:
                step_desc = f"步骤{step.step_index}: 调用 {tc.tool}"
                if tr:
                    step_desc += f" -> {'成功' if tr.ok else '失败'}"
                    if tr.error:
                        step_desc += f" ({tr.error[:100]})"
                steps.append(step_desc)
    if not steps:
        steps.append("未能生成修复步骤详情")
    return steps


def _handle_failure(
    job: RepairJob,
    failure_type: str,
    failure_report: str,
    error_msg: str,
    repair_report_url: str | None = None,
) -> None:
    status = RepairJobStatus.failed
    if "test" in failure_type:
        status = RepairJobStatus.test_failed
    elif failure_type in ("context_failed", "llm_error"):
        status = RepairJobStatus.human_required

    update_repair_job(job.job_id, status=status, last_error=error_msg[:500])

    push_event("repair_failed", {
        "job_id": job.job_id,
        "incident_id": job.incident_id,
        "issue_number": job.issue_number,
        "error": error_msg[:200],
        "failure_type": failure_type,
        "failure_report": failure_report[:500],
        "message": f"修复失败: {FAILURE_REASON_MAP.get(failure_type, error_msg[:100])}",
    })

    replace_autorepair_status_label(job.issue_number, "autorepair:human-required")

    comment_body = f"""❌ AutoRepair 修复失败，需要人工介入：

**失败类型**: {failure_type}
**失败原因**: {FAILURE_REASON_MAP.get(failure_type, '未知错误')}
**详细信息**: {error_msg[:500]}

{failure_report[:500]}
"""
    comment_issue(job.issue_number, comment_body)

    send_manual_intervention_card(
        incident_id=job.incident_id,
        issue_number=job.issue_number,
        error_message=f"[{failure_type}] {error_msg[:200]}",
        issue_url=job.issue_url or "",
        report_url=repair_report_url or "",
    )

    append_audit_event(
        "repair_failed",
        job.incident_id,
        {
            "job_id": job.job_id,
            "failure_type": failure_type,
            "error": error_msg[:500],
            "failure_report": failure_report[:500],
        },
    )


async def execute_repair_job_async(job: RepairJob) -> RepairExecutionResult:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, execute_next_repair_job)


async def process_all_queued_jobs(max_concurrent: int = 3) -> list[RepairExecutionResult]:
    processed_repos: Set[str] = set()
    running_tasks = []
    results = []

    while True:
        queued_jobs = [job for job in load_repair_jobs() if job.status == RepairJobStatus.queued]
        available_jobs = []

        for job in queued_jobs:
            repo_key = f"{job.repo_owner}/{job.repo_name}"
            if repo_key not in processed_repos and not _has_active_job_for_issue(job.issue_number):
                available_jobs.append(job)
                processed_repos.add(repo_key)

                if len(available_jobs) + len(running_tasks) >= max_concurrent:
                    break

        if not available_jobs and not running_tasks:
            break

        for job in available_jobs:
            task = asyncio.create_task(execute_repair_job_async(job))
            running_tasks.append(task)

        if running_tasks:
            done_set, pending_set = await asyncio.wait(running_tasks, return_when=asyncio.FIRST_COMPLETED)
            running_tasks = list(pending_set)
            for task in done_set:
                result = task.result()
                results.append(result)
                if result.job:
                    repo_key = f"{result.job.repo_owner}/{result.job.repo_name}"
                    processed_repos.discard(repo_key)

    return results
