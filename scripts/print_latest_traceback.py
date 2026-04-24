import sys
from pathlib import Path

# 将项目根目录加入Python路径，解决模块找不到问题
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.log_parser import read_latest_traceback, extract_error_summary
from autorepair.config import LOG_PATH

if __name__ == "__main__":
    traceback = read_latest_traceback(LOG_PATH)
    if traceback:
        print("Latest Traceback:")
        print("=" * 80)
        print(traceback)
        print("=" * 80)
        
        # 输出错误摘要
        error_summary = extract_error_summary(traceback)
        if error_summary:
            print("\nError Summary:")
            print("=" * 80)
            print(f"error_type: {error_summary.error_type}")
            print(f"message: {error_summary.message}")
            print(f"suspected_file: {error_summary.suspected_file}")
            print(f"line_no: {error_summary.line_no}")
            print(f"function: {error_summary.function}")
            print(f"fingerprint: {error_summary.fingerprint}")
            print("=" * 80)
    else:
        print("No traceback found.")
