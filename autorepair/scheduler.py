import os
import fcntl
from pathlib import Path
from typing import Optional
from .config import PROJECT_ROOT

REPAIR_LOCK_PATH = PROJECT_ROOT / "autorepair" / "records" / "locks" / "repair_worker.lock"

class Scheduler:
    def __init__(self):
        self.repair_lock_file: Optional[Path] = None
        self.repair_lock_fd: Optional[int] = None
    
    def acquire_repair_lock(self) -> bool:
        """获取修复锁，成功返回True，失败返回False"""
        REPAIR_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.repair_lock_fd = os.open(REPAIR_LOCK_PATH, os.O_CREAT | os.O_RDWR)
            # Windows上使用不同的锁机制，简化实现
            if os.name == 'nt':
                # Windows平台简单实现：检查文件是否存在且不为空
                if os.path.getsize(REPAIR_LOCK_PATH) > 0:
                    try:
                        # 尝试读取PID
                        with open(REPAIR_LOCK_PATH, 'r') as f:
                            pid = int(f.read().strip())
                        # 检查进程是否存在
                        import psutil
                        if psutil.pid_exists(pid):
                            return False
                    except:
                        pass
            else:
                # Unix平台使用fcntl锁
                fcntl.flock(self.repair_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # 写入当前进程ID
            os.ftruncate(self.repair_lock_fd, 0)
            os.write(self.repair_lock_fd, str(os.getpid()).encode())
            os.fsync(self.repair_lock_fd)
            return True
        except BlockingIOError:
            # 锁已被持有
            return False
        except Exception:
            return False
    
    def release_repair_lock(self) -> None:
        """释放修复锁"""
        if self.repair_lock_fd is not None:
            try:
                if os.name != 'nt':
                    fcntl.flock(self.repair_lock_fd, fcntl.LOCK_UN)
                os.close(self.repair_lock_fd)
                if REPAIR_LOCK_PATH.exists():
                    os.unlink(REPAIR_LOCK_PATH)
            except Exception:
                pass
            self.repair_lock_fd = None
    
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

# 全局调度器实例
scheduler = Scheduler()
