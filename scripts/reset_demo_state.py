import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.config import LOG_PATH
from autorepair.incident_store import DEFAULT_INCIDENT_PATH
from autorepair.watch_state import DEFAULT_WATCH_STATE_PATH

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
    
    print("=" * 50)
    print("🎉 演示状态清理完成！")
    print("现在可以重新开始演示流程。")
