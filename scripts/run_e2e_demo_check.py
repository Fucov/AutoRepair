import sys
import os
import re
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.config import config
from autorepair.service_registry import get_default_service
from autorepair.repair.repo_lock import DEFAULT_LOCK_DIR
from autorepair.repair.job_store import load_repair_jobs
from autorepair.adapters.github import _is_github_configured, _load_mock_issues
from autorepair.incident_store import load_incidents
from autorepair.log_parser import extract_error_summary
import subprocess
import git


def check(label: str, condition: bool, detail: str = "") -> str:
    status = "✅ PASS" if condition else "❌ FAIL"
    extra = f" - {detail}" if detail else ""
    print(f"{status} {label}{extra}")
    return status


def check_warn(label: str, condition: bool, detail: str = "") -> str:
    if condition:
        print(f"✅ PASS {label}")
        return "PASS"
    else:
        print(f"⚠️  WARN {label} - {detail}")
        return "WARN"


def main() -> int:
    print("=" * 60)
    print("FeishuAutoRepair E2E Demo 前置条件检查")
    print("=" * 60)
    
    results = []
    
    # 1. Feishu ready / mock
    feishu_ready = config.is_feishu_ready()
    results.append(check("飞书配置", feishu_ready, "ready" if feishu_ready else "mock模式"))
    
    # 2. GitHub ready / mock
    github_ready = _is_github_configured()
    results.append(check("GitHub配置", True, "ready" if github_ready else "mock模式"))
    
    # 3. Ark ready / mock
    ark_ready = bool(os.getenv("ARK_API_KEY") and os.getenv("ARK_MODEL_REPAIR"))
    results.append(check("Doubao(Ark)配置", True, "ready" if ark_ready else "mock模式，需要手动提供patch"))
    
    # 4. 工作区是否干净
    try:
        repo = git.Repo(Path(__file__).parent.parent)
        is_clean = len(repo.untracked_files) == 0 and not repo.index.diff(None)
        results.append(check_warn("Git工作区干净", is_clean, "有未提交的文件，可能影响worktree创建"))
    except Exception as e:
        results.append(check_warn("Git工作区检查", False, str(e)))
    
    # 5. demo service 是否可访问
    service = get_default_service()
    service_exists = Path(service.repo_path).exists()
    results.append(check("Demo服务存在", service_exists, service.repo_path))
    
    # 6. services.yaml 是否可读取
    from autorepair.service_registry import DEFAULT_CONFIG_PATH
    services_yaml_exists = Path(DEFAULT_CONFIG_PATH).exists()
    results.append(check("services.yaml", services_yaml_exists, str(DEFAULT_CONFIG_PATH)))
    
    # 7. Template IDs 是否配置
    from autorepair.adapters.feishu import FEISHU_CARD_TEMPLATES
    templates_configured = len(FEISHU_CARD_TEMPLATES) > 0
    results.append(check("飞书卡片模板", templates_configured, f"{len(FEISHU_CARD_TEMPLATES)}个模板"))
    
    # 8. repo lock 是否可用
    lock_dir_exists = DEFAULT_LOCK_DIR.parent.exists()
    results.append(check("repo lock目录", lock_dir_exists, str(DEFAULT_LOCK_DIR.parent)))
    
    # 9. 是否存在未清理worktree
    try:
        worktrees = []
        worktrees_base = Path(service.repo_path) / ".worktrees"
        if worktrees_base.exists():
            worktrees = list(worktrees_base.iterdir())
        results.append(check_warn("无残留worktree", len(worktrees) == 0, f"发现{len(worktrees)}个未清理的worktree"))
    except Exception as e:
        results.append(check_warn("worktree检查", False, str(e)))
    
    # 10. 检查pytest是否可用
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True, text=True, timeout=5
        )
        pytest_available = result.returncode == 0
        results.append(check("pytest可用", pytest_available, result.stdout.strip() if pytest_available else ""))
    except Exception:
        results.append(check("pytest可用", False, "pytest命令执行失败"))

    # 11. 检查 ticket-timezone-sla 主线Bug是否能被正确触发
    try:
        from demo_service.ticket_service import submit_ticket
        test_payload = {
            "customer_id": "c_check",
            "title": "检查主线Bug",
            "priority": "P1",
            "channel": "feishu",
            "sla_deadline": "2099-01-01T18:00:00+08:00",
            "idempotency_key": "evt_check_001"
        }
        bug_triggered = False
        bug_type_ok = False
        try:
            submit_ticket(test_payload)
        except TypeError as e:
            bug_triggered = True
            error_msg = str(e).lower()
            if "offset-naive" in error_msg or "offset-aware" in error_msg or "timezone" in error_msg:
                bug_type_ok = True
        results.append(check(
            "ticket-timezone-sla主线Bug",
            bug_triggered and bug_type_ok,
            "TypeError: can't compare offset-naive and offset-aware datetimes"
            if (bug_triggered and bug_type_ok)
            else ("未触发TypeError" if not bug_triggered else "错误类型不匹配")
        ))
    except Exception as e:
        results.append(check("ticket-timezone-sla主线Bug", False, str(e)))

    # 12. 检查 log_parser 能正确提取主线Bug特征
    try:
        sample_traceback = '''Traceback (most recent call last):
  File "demo_service/ticket_service.py", line 30, in submit_ticket
    if deadline < datetime.utcnow():
TypeError: can't compare offset-naive and offset-aware datetimes'''
        summary = extract_error_summary(sample_traceback)
        parser_ok = (
            summary is not None
            and summary.error_type == "TypeError"
            and "ticket_service.py" in (summary.suspected_file or "")
        )
        results.append(check(
            "log_parser提取主线Bug",
            parser_ok,
            f"{summary.error_type} at {summary.suspected_file}:{summary.line_no}" if summary else "无法提取"
        ))
    except Exception as e:
        results.append(check("log_parser提取主线Bug", False, str(e)))
    
    # 汇总
    print("\n" + "=" * 60)
    fail_count = sum(1 for r in results if r == "FAIL")
    warn_count = sum(1 for r in results if r == "WARN")
    pass_count = sum(1 for r in results if r == "PASS")
    
    print(f"结果: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL")
    
    if fail_count > 0:
        print("状态: ❌ 不满足演示条件，请先修复FAIL项")
        return 1
    elif warn_count > 0:
        print("状态: ⚠️  可以演示，但存在警告项")
        return 0
    else:
        print("状态: ✅ 满足所有演示条件")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
