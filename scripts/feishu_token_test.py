import sys
sys.path.insert(0, sys.path[0] + "/..")

from autorepair.adapters.feishu import get_tenant_access_token
from autorepair.config import config

def main():
    if not config.is_feishu_ready():
        print("Feishu config not ready, cannot test token")
        return
    
    token, err = get_tenant_access_token()
    if err:
        print(f"token acquired: no")
        print(f"error: {err}")
    else:
        print(f"token acquired: yes")
        # 不打印真实token
        print(f"expire: 7200 seconds (default)")

if __name__ == "__main__":
    main()
