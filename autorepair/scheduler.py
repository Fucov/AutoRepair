import os
from pathlib import Path
from typing import Optional
from .config import PROJECT_ROOT

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

# 全局调度器实例
scheduler = Scheduler()
