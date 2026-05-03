from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Set
from pydantic import BaseModel
from autorepair.adapters.llm_client import LLMClient as ArkClient
from autorepair.adapters.github import (
    find_open_pr_for_branch,
    create_pull_request,
    comment_issue,
    replace_autorepair_status_label,
    add_labels,
)
from autorepair.adapters.feishu import send_manual_intervention_card, send_fix_pr_ready_card
from autorepair.audit_store import append_audit_event
from autorepair.dashboard.api import push_event
from autorepair.incident_store import get_incident_by_id
from autorepair.repair.context_collector import collect_repair_context
from autorepair.repair.git_workspace import (
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
from autorepair.repair.patch_applier import apply_patch_plan
from autorepair.repair.patch_prompt import build_patch_prompt
from autorepair.repair.patch_schema import PatchPlan
from autorepair.repair.repo_lock import acquire_repo_lock
from autorepair.repair.schemas import RepairJobStatus, RepairJob
from autorepair.repair.test_runner import run_command_in_worktree


class RepairExecutionResult(BaseModel):
    success: bool
    job: RepairJob | None = None
    error: str | None = None


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
            error=f"Active job or open PR already exists for issue #{job.issue_number}"
        )

    repo_key = f"{job.repo_owner}/{job.repo_name}"
    with acquire_repo_lock(repo_key) as lock:
        if not lock.acquired:
            return RepairExecutionResult(
                success=True,
                error=f"Repo lock busy for {repo_key}; job remains queued"
            )

        try:
            update_repair_job(job.job_id, status=RepairJobStatus.running)
            replace_autorepair_status_label(job.issue_number, "autorepair:repairing")

            push_event("repair_started", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "issue_number": job.issue_number,
                "message": f"修复任务 {job.job_id} 开始执行"
            })

            incident = get_incident_by_id(job.incident_id)
            if not incident:
                raise ValueError(f"Incident {job.incident_id} not found")

            context = collect_repair_context(job, incident, job.worktree_path)
            append_audit_event(
                "repair_context_collected",
                job.incident_id,
                {"job_id": job.job_id, "snippets": list(context.code_snippets.keys())}
            )

            push_event("repair_context_collected", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "snippets": list(context.code_snippets.keys()),
                "message": "修复上下文收集完成"
            })

            ark_client = ArkClient()
            messages = build_patch_prompt(context)
            
            max_retries = 2
            patch_plan = None
            test_result = None
            
            for attempt in range(max_retries):
                try:
                    patch_plan_dict = ark_client.chat_json(messages, temperature=0.1 if attempt == 0 else 0.3)
                    patch_plan = PatchPlan.model_validate(patch_plan_dict)
                    append_audit_event(
                        "patch_plan_generated",
                        job.incident_id,
                        {
                            "job_id": job.job_id,
                            "attempt": attempt + 1,
                            "summary": patch_plan.summary,
                            "files": [f.path for f in patch_plan.files],
                            "confidence": patch_plan.confidence
                        }
                    )

                    push_event("patch_plan_generated", {
                        "job_id": job.job_id,
                        "incident_id": job.incident_id,
                        "attempt": attempt + 1,
                        "summary": patch_plan.summary,
                        "files": [f.path for f in patch_plan.files],
                        "confidence": patch_plan.confidence,
                        "message": f"补丁方案生成完成（第{attempt + 1}次尝试）"
                    })

                    apply_result = apply_patch_plan(patch_plan, job.worktree_path)
                    if not apply_result.ok:
                        raise ValueError(f"Patch apply failed: {apply_result.error}")
                    
                    append_audit_event(
                        "patch_applied",
                        job.incident_id,
                        {"job_id": job.job_id, "changed_files": apply_result.changed_files}
                    )

                    push_event("patch_applied", {
                        "job_id": job.job_id,
                        "incident_id": job.incident_id,
                        "changed_files": apply_result.changed_files,
                        "message": "补丁已应用到代码"
                    })

                    test_result = run_command_in_worktree(context.target_test_command, job.worktree_path)
                    if test_result.returncode == 0:
                        break
                    
                    error_msg = f"Test failed on attempt {attempt + 1}:\nstdout:\n{test_result.stdout}\nstderr:\n{test_result.stderr}"
                    messages.append({"role": "assistant", "content": str(patch_plan.model_dump_json())})
                    messages.append({"role": "user", "content": f"修复失败，测试运行错误：{error_msg}\n请重新生成修复方案。"})
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    continue
            
            if not test_result or test_result.returncode != 0:
                raise ValueError(f"Target test failed after {max_retries} attempts: {test_result.stderr if test_result else 'No test result'}")
            
            full_test_result = run_command_in_worktree(context.full_test_command, job.worktree_path)
            if full_test_result.returncode != 0:
                raise ValueError(f"Full test suite failed: {full_test_result.stderr}")
            
            diff = get_git_diff(job.worktree_path)
            if not diff.strip():
                raise ValueError("No code changes to commit")
            
            commit_message = f"""fix: normalize SLA deadline timezone comparison

Incident: {job.incident_id}
Issue: #{job.issue_number}
Test: {context.target_test_command}
"""
            commit_sha = git_commit_all(job.worktree_path, commit_message)
            append_audit_event(
                "code_committed",
                job.incident_id,
                {"job_id": job.job_id, "commit_sha": commit_sha}
            )

            push_event("code_committed", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "commit_sha": commit_sha,
                "message": "代码已提交到修复分支"
            })

            git_push_branch(job.worktree_path, job.repair_branch)
            append_audit_event(
                "branch_pushed",
                job.incident_id,
                {"job_id": job.job_id, "branch": job.repair_branch}
            )

            push_event("branch_pushed", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "branch": job.repair_branch,
                "message": "修复分支已推送到远程"
            })

            pr_title = "[AutoRepair] Fix timezone-aware SLA deadline comparison"
            pr_body = f"""## AutoRepair Fix
Incident ID: {job.incident_id}
Related Issue: #{job.issue_number}

### Root Cause
Timezone-aware datetime object compared with naive datetime object in SLA deadline calculation.

### Fix Summary
{patch_plan.summary if patch_plan else "Normalize all datetime objects to UTC timezone before comparison."}

### Tests
- Target test: {context.target_test_command}
- Full test suite: {context.full_test_command}

### Risk Level
{patch_plan.risk_level if patch_plan else "low"}
### Confidence
{patch_plan.confidence if patch_plan else 0.9}

### Diff
```diff
{diff}
```
"""
            pr = create_pull_request(pr_title, pr_body, job.repair_branch, job.base_branch)
            if not pr:
                raise ValueError("Failed to create pull request")
            
            update_repair_job(
                job.job_id,
                status=RepairJobStatus.pr_created,
                pr_number=pr.number,
                pr_url=pr.html_url,
                last_error=None
            )

            push_event("pr_created", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "issue_number": job.issue_number,
                "pr_number": pr.number,
                "pr_url": pr.html_url,
                "message": f"PR #{pr.number} 创建成功"
            })

            replace_autorepair_status_label(job.issue_number, "autorepair:pr-ready")
            add_labels(job.issue_number, [f"risk:{patch_plan.risk_level if patch_plan else 'low'}"])
            
            comment_body = f"""✅ AutoRepair 已生成修复PR：[#{pr.number}]({pr.html_url})
修复摘要：{patch_plan.summary if patch_plan else '修复时区比较问题'}
测试已通过，请人工Review。
"""
            comment_issue(job.issue_number, comment_body)
            
            send_fix_pr_ready_card(
                incident_id=job.incident_id,
                issue_number=job.issue_number,
                pr_url=pr.html_url,
                pr_title=pr_title,
                fix_summary=patch_plan.summary if patch_plan else '修复时区比较问题',
                risk_level=patch_plan.risk_level if patch_plan else 'low'
            )

            push_event("card_sent", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "card_type": "fix_pr_ready",
                "message": "PR修复完成卡片已发送到飞书"
            })

            append_audit_event(
                "pr_created",
                job.incident_id,
                {
                    "job_id": job.job_id,
                    "pr_number": pr.number,
                    "pr_url": pr.html_url
                }
            )

            push_event("repair_completed", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "issue_number": job.issue_number,
                "pr_number": pr.number,
                "pr_url": pr.html_url,
                "message": f"修复完成！PR #{pr.number} 已创建"
            })

            return RepairExecutionResult(success=True, job=job)
            
        except Exception as e:
            error_msg = str(e)
            update_repair_job(
                job.job_id,
                status=RepairJobStatus.test_failed if "test" in error_msg.lower() else RepairJobStatus.failed,
                last_error=error_msg
            )

            push_event("repair_failed", {
                "job_id": job.job_id,
                "incident_id": job.incident_id,
                "issue_number": job.issue_number,
                "error": error_msg,
                "message": f"修复失败: {error_msg[:100]}"
            })

            replace_autorepair_status_label(job.issue_number, "autorepair:human-required")
            
            comment_body = f"""❌ AutoRepair 修复失败，需要人工介入：
错误信息：{error_msg}
"""
            comment_issue(job.issue_number, comment_body)
            
            send_manual_intervention_card(
                incident_id=job.incident_id,
                issue_number=job.issue_number,
                error_message=error_msg
            )
            
            append_audit_event(
                "repair_failed",
                job.incident_id,
                {"job_id": job.job_id, "error": error_msg}
            )
            
            try:
                remove_repair_worktree(job.worktree_path)
            except:
                pass
            
            return RepairExecutionResult(success=False, job=job, error=error_msg)


async def execute_repair_job_async(job: RepairJob) -> RepairExecutionResult:
    """异步执行单个修复任务"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, execute_next_repair_job)


async def process_all_queued_jobs(max_concurrent: int = 3) -> list[RepairExecutionResult]:
    """异步处理所有排队中的任务，不同仓库可并发执行"""
    processed_repos: Set[str] = set()
    running_tasks = []
    results = []
    
    while True:
        # 收集所有可执行的任务（不同仓库的）
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
            
        # 启动新的任务
        for job in available_jobs:
            task = asyncio.create_task(execute_repair_job_async(job))
            running_tasks.append(task)
        
        # 等待任意任务完成
        if running_tasks:
            done, running_tasks = await asyncio.wait(running_tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                result = task.result()
                results.append(result)
                if result.job:
                    repo_key = f"{result.job.repo_owner}/{result.job.repo_name}"
                    processed_repos.discard(repo_key)
    
    return results
