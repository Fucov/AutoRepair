import sys
from pathlib import Path

# 将项目根目录加入Python路径，解决模块找不到问题
sys.path.append(str(Path(__file__).parent.parent.resolve()))

import httpx

if __name__ == "__main__":
    try:
        response = httpx.get("http://127.0.0.1:8000/users/not-exist/profile")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
