import os
import logging
import threading
from pathlib import Path
from typing import Optional
from .config import PROJECT_ROOT

logger = logging.getLogger(__name__)

# 条件导入fcntl，仅Unix平台可用
if os.name != 'nt':
    import fcntl
else:
    fcntl = None

REPAIR_LOCK_PATH = PROJECT_ROOT / "autorepair" / "records" / "locks" / "repair_worker.lock"

class Scheduler:
    def __init__(self):
        self.repair_lock_file: Optional[Path] = None
        self.repair_lock_fd: Optional[int] = None
    
    def acquire_repair_lock(self) -> bool:
        """获取修复锁，成功返回True，失败返回False"""
        REPAIR_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Windows平台简化实现：基于PID文件的锁
            if os.name == 'nt':
                if REPAIR_LOCK_PATH.exists():
                    try:
                        # 读取文件中的PID
                        with open(REPAIR_LOCK_PATH, 'r') as f:
                            pid = int(f.read().strip())
                        # 检查进程是否存在
                        try:
                            import psutil
                            if psutil.pid_exists(pid):
                                return False
                        except ImportError:
                            # 如果没有psutil，直接认为文件存在就是有锁
                            return False
                    except:
                        # 文件损坏，直接覆盖
                        pass
                
                # 写入当前PID
                with open(REPAIR_LOCK_PATH, 'w') as f:
                    f.write(str(os.getpid()))
                self.repair_lock_file = REPAIR_LOCK_PATH
                return True
            else:
                # Unix平台使用fcntl锁
                self.repair_lock_fd = os.open(REPAIR_LOCK_PATH, os.O_CREAT | os.O_RDWR)
                fcntl.flock(self.repair_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # 写入当前进程ID
                os.ftruncate(self.repair_lock_fd, 0)
                os.write(self.repair_lock_fd, str(os.getpid()).encode())
                os.fsync(self.repair_lock_fd)
                return True
        except BlockingIOError:
            # 锁已被持有
            return False
        except Exception as e:
            print(f"获取锁失败: {str(e)}")
            return False
    
    def release_repair_lock(self) -> None:
        """释放修复锁"""
        try:
            if os.name == 'nt':
                # Windows平台删除PID文件
                if self.repair_lock_file and self.repair_lock_file.exists():
                    self.repair_lock_file.unlink()
                    self.repair_lock_file = None
            else:
                # Unix平台释放fcntl锁
                if self.repair_lock_fd is not None:
                    fcntl.flock(self.repair_lock_fd, fcntl.LOCK_UN)
                    os.close(self.repair_lock_fd)
                    if REPAIR_LOCK_PATH.exists():
                        os.unlink(REPAIR_LOCK_PATH)
                    self.repair_lock_fd = None
        except Exception as e:
            print(f"释放锁失败: {str(e)}")
    
    def is_repair_running(self) -> bool:
        """检查是否有修复任务正在运行"""
        if not REPAIR_LOCK_PATH.exists():
            return False
        
        try:
            if os.name == 'nt':
                # Windows平台检查
                with open(REPAIR_LOCK_PATH, 'r') as f:
                    pid = int(f.read().strip())
                import psutil
                return psutil.pid_exists(pid)
            else:
                # Unix平台检查锁
                fd = os.open(REPAIR_LOCK_PATH, os.O_RDONLY)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    # 能获取锁说明没有运行的进程
                    return False
                except BlockingIOError:
                    return True
                finally:
                    os.close(fd)
        except Exception:
            return False

class IssuePoller:
    def __init__(self, interval: int | None = None):
        self._interval = interval or int(os.getenv("ISSUE_POLL_INTERVAL", "30"))
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._processed_issues: set[int] = set()
        self._last_poll_at: str | None = None
        self._total_processed: int = 0
        self._last_error: str | None = None

    def start(self) -> None:
        if self._running:
            logger.warning("IssuePoller 已在运行中")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="IssuePoller")
        self._thread.start()
        self._running = True
        logger.info(f"IssuePoller 启动，轮询间隔: {self._interval}秒")

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        self._running = False
        logger.info("IssuePoller 已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "interval_seconds": self._interval,
            "total_processed": self._total_processed,
            "last_poll_at": self._last_poll_at,
            "last_error": self._last_error,
            "pending_count": len(self._processed_issues),
        }

    def _poll_loop(self) -> None:
        from datetime import datetime
        while not self._stop_event.is_set():
            try:
                self._last_poll_at = datetime.now().isoformat()
                self._poll_once()
                self._last_error = None
            except Exception as e:
                self._last_error = str(e)
                logger.error(f"IssuePoller 轮询失败: {e}", exc_info=True)
            self._stop_event.wait(self._interval)

    def _poll_once(self) -> None:
        from autorepair.adapters.github import list_open_bug_issues
        from autorepair.repair.orchestrator import process_issue_for_repair
        from autorepair.dashboard.api import push_event

        issues = list_open_bug_issues()
        if not issues:
            return

        for issue in issues:
            if issue.number in self._processed_issues:
                continue

            labels = issue.labels
            if "bug" not in labels:
                continue

            already_active_labels = {
                "autorepair:repairing",
                "autorepair:pr-ready",
                "autorepair:closed",
                "autorepair:human-required",
            }
            if already_active_labels & set(labels):
                self._processed_issues.add(issue.number)
                continue

            try:
                job = process_issue_for_repair(issue.number)
                self._processed_issues.add(issue.number)
                self._total_processed += 1

                push_event("issue_polled", {
                    "issue_number": issue.number,
                    "issue_title": issue.title,
                    "job_id": job.job_id if job else None,
                    "accepted": job is not None,
                    "message": f"Issue #{issue.number} 自动轮询{'已接受' if job else '未通过'}",
                })
            except Exception as e:
                logger.error(f"IssuePoller 处理 Issue #{issue.number} 失败: {e}", exc_info=True)
                self._processed_issues.add(issue.number)


# 全局调度器实例
scheduler = Scheduler()
issue_poller = IssuePoller()
