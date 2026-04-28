import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.adapters.github import replace_autorepair_status_label
from autorepair.audit_store import append_audit_event
from autorepair.repair.git_workspace import create_repair_worktree
from autorepair.repair.job_store import find_oldest_queued_job, update_repair_job
from autorepair.repair.repo_lock import acquire_repo_lock
from autorepair.repair.schemas import RepairJobStatus


def main() -> int:
    job = find_oldest_queued_job()
    if not job:
        print("No queued repair job.")
        return 0

    repo_key = f"{job.repo_owner}/{job.repo_name}"
    with acquire_repo_lock(repo_key) as lock:
        if not lock.acquired:
            print(f"Repo lock busy for {repo_key}; job remains queued: {job.job_id}")
            return 0

        update_repair_job(job.job_id, status=RepairJobStatus.running)
        replace_autorepair_status_label(job.issue_number, "autorepair:repairing")
        try:
            info = create_repair_worktree(
                repo_path=Path(job.worktree_path).parent.parent,
                base_branch=job.base_branch,
                repair_branch=job.repair_branch,
                incident_id=job.incident_id,
            )
            append_audit_event(
                "repair_worker_dry_run",
                job.incident_id,
                {
                    "job_id": job.job_id,
                    "worktree_path": info.worktree_path,
                    "repair_branch": info.repair_branch,
                    "would_patch": True,
                },
            )
            update_repair_job(
                job.job_id,
                status=RepairJobStatus.running,
                worktree_path=info.worktree_path,
                last_error="dry-run: worktree created; no patch or PR created in Stage 3A",
            )
            print(f"Dry-run repair workspace ready: {info.worktree_path}")
            return 0
        except Exception as exc:
            update_repair_job(job.job_id, status=RepairJobStatus.failed, last_error=str(exc))
            append_audit_event("repair_worker_failed", job.incident_id, {"job_id": job.job_id, "error": str(exc)})
            print(f"Repair job failed: {exc}")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
