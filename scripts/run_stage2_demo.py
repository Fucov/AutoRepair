import sys
from pathlib import Path

# 将项目根目录加入Python路径
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from autorepair.watcher import scan_latest_log_once
from autorepair.adapters.feishu import send_incident_card

if __name__ == "__main__":
    print("🚀 Stage 2A 演示流程")
    print("=" * 50)
    print("请先确保已在另一个终端执行以下命令启动服务:")
    print("  python scripts/run_demo_server.py")
    print("\n然后请访问 http://127.0.0.1:8000/ 并点击「触发 Bug」按钮")
    input("\n触发Bug后按 Enter 键继续...")

    # 扫描日志
    print("\n🔍 正在扫描最新日志...")
    incident = scan_latest_log_once()

    if incident:
        print(f"\n✅ 发现新 Incident: {incident.incident_id}")
        # 发送飞书卡片
        send_incident_card(incident)
        print(f"\n📝 Incident 已记录到 autorepair/records/incidents.jsonl")
    else:
        print("\nℹ️  未发现新的异常 Incident")
        print("请先确保已触发 Bug，再重新运行本脚本")
