import sys
from pathlib import Path

# 将项目根目录加入Python路径，解决模块找不到问题
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

# 强制清除模块缓存
for module in list(sys.modules.keys()):
    if module.startswith('demo_service'):
        del sys.modules[module]

import uvicorn
from demo_service.app import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        reload=False,  # 关闭自动重载，避免缓存问题和字符串导入要求
    )
