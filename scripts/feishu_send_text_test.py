import sys
sys.path.insert(0, sys.path[0] + "/..")

from autorepair.adapters.feishu import send_text_message
from autorepair.config import config

def main():
    if not config.is_feishu_ready():
        print("Feishu mode: mock, reason: missing configuration")
    else:
        print("Feishu mode: real")
    
    content = "AutoRepair Feishu text smoke test."
    result, err = send_text_message(content)
    
    if err:
        print(f"Send failed: {err}")
    else:
        if result.get("mock"):
            print("Mock message sent successfully")
        else:
            print(f"Send success! Message ID: {result['data']['message_id']}")

if __name__ == "__main__":
    main()
