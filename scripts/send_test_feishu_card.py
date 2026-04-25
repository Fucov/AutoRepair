import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from autorepair.adapters.feishu import send_incident_card
from autorepair.schemas import Incident
from autorepair.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID

load_dotenv()

def send_test_feishu_card():
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
    
    try:
        send_incident_card(incident)
        if all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID]):
            print("Feishu card sent successfully")
        else:
            print("Feishu config missing, fallback to mock card")
    except Exception as e:
        print(f"Error sending Feishu card: {str(e)}")
        print("Fallback to mock card")

if __name__ == "__main__":
    send_test_feishu_card()
