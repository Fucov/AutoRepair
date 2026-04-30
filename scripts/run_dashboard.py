#!/usr/bin/env python3
"""
启动Dashboard服务
Usage: python scripts/run_dashboard.py [--host 0.0.0.0] [--port 8888]
"""
import argparse
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from autorepair.dashboard.api import run_server

def main():
    parser = argparse.ArgumentParser(description="启动FeishuAutoRepair Dashboard服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8888, help="监听端口 (默认: 8888)")
    
    args = parser.parse_args()
    
    print(f"🚀 启动Dashboard服务，监听地址: http://{args.host}:{args.port}")
    print(f"📊 访问 http://localhost:{args.port} 查看Dashboard")
    print("按 Ctrl+C 停止服务")
    
    run_server(host=args.host, port=args.port)

if __name__ == "__main__":
    main()
