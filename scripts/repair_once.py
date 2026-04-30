import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.repair.executor import execute_next_repair_job


def main() -> int:
    result = execute_next_repair_job()
    
    if not result.success:
        print(f"Repair job failed: {result.error}")
        return 1
    
    if result.error:
        print(result.error)
        return 0
    
    if result.job:
        print(f"Repair job completed successfully: {result.job.job_id}")
        if result.job.pr_url:
            print(f"PR created: {result.job.pr_url}")
        return 0
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
