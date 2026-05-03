import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.config import LOG_PATH, PROJECT_ROOT
from autorepair.incident_store import DEFAULT_INCIDENT_PATH
from autorepair.watch_state import DEFAULT_WATCH_STATE_PATH
from autorepair.adapters.github import (
    MOCK_GITHUB_ISSUES_PATH,
    MOCK_GITHUB_ISSUE_COMMENTS_PATH,
    MOCK_GITHUB_PRS_PATH,
)
from autorepair.audit_store import DEFAULT_AUDIT_PATH
from autorepair.repair.job_store import DEFAULT_REPAIR_JOBS_PATH

# 直接定义锁文件路径，避免导入scheduler模块
REPAIR_LOCK_PATH = PROJECT_ROOT / "autorepair" / "records" / "locks" / "repair_worker.lock"

def reset_file(file_path: Path, description: str):
    """重置文件内容"""
    try:
        if file_path.exists():
            # 清空文件内容，不删除文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("")
            print(f"✅ 已清空 {description}: {file_path}")
        else:
            print(f"ℹ️  {description} 不存在，无需清空: {file_path}")
    except Exception as e:
        print(f"⚠️  清空{description}失败: {str(e)}")

def delete_file(file_path: Path, description: str):
    """删除文件"""
    try:
        if file_path.exists():
            file_path.unlink()
            print(f"✅ 已删除 {description}: {file_path}")
        else:
            print(f"ℹ️  {description} 不存在，无需删除: {file_path}")
    except Exception as e:
        print(f"⚠️  删除{description}失败: {str(e)}")

if __name__ == "__main__":
    print("🧹 开始清理演示状态...")
    print("=" * 50)
    
    # 1. 清空日志文件
    reset_file(LOG_PATH, "日志文件")
    
    # 2. 清空Incident记录
    reset_file(DEFAULT_INCIDENT_PATH, "Incident记录文件")
    
    # 3. 删除watch状态文件
    delete_file(DEFAULT_WATCH_STATE_PATH, "Watch状态文件")
    
    # 4. 清空Mock GitHub Issue文件
    reset_file(MOCK_GITHUB_ISSUES_PATH, "Mock GitHub Issue记录文件")
    
    # 5. 清空Mock GitHub Issue评论文件
    reset_file(MOCK_GITHUB_ISSUE_COMMENTS_PATH, "Mock GitHub Issue评论文件")
    
    # 6. 清空审计记录文件
    reset_file(MOCK_GITHUB_PRS_PATH, "Mock GitHub PR记录文件")

    # 7. 清空审计记录文件
    reset_file(DEFAULT_AUDIT_PATH, "审计记录文件")
    
    # 8. 清空RepairJob记录文件
    reset_file(DEFAULT_REPAIR_JOBS_PATH, "修复任务记录文件")
    
    # 9. 删除修复锁文件
    delete_file(REPAIR_LOCK_PATH, "修复任务锁文件")
    
    # 10. 清空本地诊断报告目录
    reports_dir = PROJECT_ROOT / "autorepair" / "records" / "reports"
    if reports_dir.exists():
        import shutil
        for file in reports_dir.glob("*.md"):
            try:
                file.unlink()
                print(f"✅ 已删除报告文件: {file.name}")
            except Exception as e:
                print(f"⚠️  删除报告文件失败: {file.name}, 错误: {str(e)}")
    
    print("=" * 50)
    print("🎉 演示状态清理完成！")
    print("现在可以重新开始演示流程。")
