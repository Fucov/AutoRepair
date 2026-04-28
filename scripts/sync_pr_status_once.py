import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters import feishu
from autorepair.adapters.github import (
    close_issue,
    comment_issue,
    get_pull_request,
    replace_autorepair_status_label,
)
from autorepair.audit_store import append_audit_event
from autorepair.repair.git_workspace import (
    delete_local_branch,
    delete_remote_branch,
    remove_repair_worktree,
)
from autorepair.repair.job_store import DEFAULT_REPAIR_JOBS_PATH, load_repair_jobs, update_repair_job
from autorepair.repair.schemas import RepairJobStatus


def sync_once() -> int:
    jobs = [job for job in load_repair_jobs(DEFAULT_REPAIR_JOBS_PATH) if job.status == RepairJobStatus.pr_created]
    if not jobs:
        print("No PR-created repair jobs to sync.")
        return 0

    for job in jobs:
        if job.pr_number is None:
            continue
        pr = get_pull_request(job.pr_number)
        if pr is None or pr.state == "open":
            continue

        if pr.merged:
            comment_issue(job.issue_number, f"AutoRepair PR #{job.pr_number} has been merged. Closing this Issue.")
            close_issue(job.issue_number)
            replace_autorepair_status_label(job.issue_number, "autorepair:closed")
            cleanup_errors: list[str] = []
            for cleanup in (
                lambda: remove_repair_worktree(job.worktree_path),
                lambda: delete_local_branch(job.repair_branch),
                lambda: delete_remote_branch(job.repair_branch),
            ):
                try:
                    cleanup()
                except Exception as exc:
                    cleanup_errors.append(str(exc))

            update_repair_job(
                job.job_id,
                path=DEFAULT_REPAIR_JOBS_PATH,
                status=RepairJobStatus.merged,
                last_error="; ".join(cleanup_errors) if cleanup_errors else None,
            )
            append_audit_event(
                "repair_pr_merged_synced",
                job.incident_id,
                {"job_id": job.job_id, "pr_number": job.pr_number, "cleanup_errors": cleanup_errors},
            )
            print(f"Synced merged PR #{job.pr_number} for Issue #{job.issue_number}")
            continue

        comment_issue(
            job.issue_number,
            f"AutoRepair PR #{job.pr_number} was closed without merge. Human review is required.",
        )
        replace_autorepair_status_label(job.issue_number, "autorepair:human-required")
        update_repair_job(
            job.job_id,
            path=DEFAULT_REPAIR_JOBS_PATH,
            status=RepairJobStatus.human_required,
            last_error="PR closed without merge",
        )
        append_audit_event(
            "repair_pr_closed_unmerged",
            job.incident_id,
            {"job_id": job.job_id, "pr_number": job.pr_number},
        )
        feishu.send_manual_intervention(
            incident_id=job.incident_id,
            service_name=job.repo_name,
            reason_brief="PR closed without merge",
            evidence_brief=f"PR #{job.pr_number}",
            suggested_action="Review the closed PR and decide whether to reopen or handle manually.",
            issue_url="",
        )
        print(f"PR #{job.pr_number} closed without merge; marked human-required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(sync_once())
