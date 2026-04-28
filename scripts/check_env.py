import sys
import argparse
sys.path.insert(0, sys.path[0] + "/..")

from autorepair.config import config

def check_env(strict: bool = False):
    print("[Feishu]")
    print(f"FEISHU_APP_ID      {'OK' if config.FEISHU_APP_ID else 'MISSING'}")
    print(f"FEISHU_APP_SECRET  {'OK' if config.FEISHU_APP_SECRET else 'MISSING'}")
    print(f"FEISHU_CHAT_ID     {'OK' if config.FEISHU_CHAT_ID else 'MISSING'}")
    print("[Ark]")
    print(f"ARK_API_KEY        {'OK' if config.ARK_API_KEY else 'MISSING'}")
    print(f"ARK_MODEL_REPAIR   {'OK' if config.ARK_MODEL_REPAIR else 'MISSING'}")
    print(f"ARK_MODEL_SUMMARY  {'OK' if config.ARK_MODEL_SUMMARY else 'MISSING'}")
    print()
    print("Summary:")
    print(f"Feishu ready: {'yes' if config.is_feishu_ready() else 'no'}")
    print(f"GitHub ready: {'yes' if config.is_github_ready() else 'no'}")
    print(f"Ark ready: {'yes' if config.is_ark_ready() else 'no'}")
    
    if strict and not (config.is_feishu_ready() and config.is_github_ready() and config.is_ark_ready()):
        print("\nError: Missing required configuration (--strict mode enabled)")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check environment variables for AutoRepair")
    parser.add_argument("--strict", action="store_true", help="Exit with error if any configuration is missing")
    args = parser.parse_args()
    check_env(args.strict)
