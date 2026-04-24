import sys
from pathlib import Path

# 将项目根目录加入Python路径，解决模块找不到问题
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.log_parser import read_latest_traceback
from autorepair.config import LOG_PATH

if __name__ == "__main__":
    traceback = read_latest_traceback(LOG_PATH)
    if traceback:
        print("Latest Traceback:")
        print("=" * 80)
        print(traceback)
        print("=" * 80)
    else:
        print("No traceback found.")
