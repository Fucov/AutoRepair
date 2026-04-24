import sys
from pathlib import Path

# 将项目根目录加入Python路径，解决模块找不到问题
sys.path.append(str(Path(__file__).parent.parent.resolve()))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "demo_service.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
