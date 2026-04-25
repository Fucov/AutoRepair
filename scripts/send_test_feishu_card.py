import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autorepair.adapters.feishu import send_incident_card
from autorepair.schemas import Incident
from autorepair.config import config

def send_test_feishu_card():
    # 先输出模式
    if config.is_feishu_ready():
        print("Feishu mode: real")
    else:
        missing = []
        if not config.FEISHU_APP_ID:
            missing.append("FEISHU_APP_ID")
        if not config.FEISHU_APP_SECRET:
            missing.append("FEISHU_APP_SECRET")
        if not config.FEISHU_CHAT_ID:
            missing.append("FEISHU_CHAT_ID")
        print(f"Feishu mode: mock, reason: missing {', '.join(missing)}")
    
    # 构造测试Incident
    incident = Incident(
        incident_id="INC-20260425-000000-SMOKE",
        source="manual",
        service="Acme SupportDesk Lite",
        service_id="demo_service",
        status="new",
        raw_traceback="This is a test traceback for smoke test",
        created_at="2026-04-25T13:00:00+08:00",
        updated_at="2026-04-25T13:00:00+08:00",
        error_summary={
            "error_type": "SmokeTest",
            "message": "Feishu integration smoke test",
            "suspected_file": "smoke_test.py",
            "line_no": 1,
            "fingerprint": "smoke-test-000000"
        }
    )
    
    result = send_incident_card(incident)
    if result and result.get("mock"):
        # mock模式下send_incident_card已经输出了卡片，这里不需要重复输出
        pass
    elif result:
        print(f"Feishu card sent successfully, message_id: {result.get('data', {}).get('message_id')}")
    else:
        print("Feishu card send failed, fallback to local notification")

if __name__ == "__main__":
    send_test_feishu_card()
