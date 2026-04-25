import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from dotenv import load_dotenv

load_dotenv()

def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}****{secret[-4:]}"

def check_env(strict: bool = False):
    feishu_vars = [
        ("FEISHU_APP_ID", os.getenv("FEISHU_APP_ID")),
        ("FEISHU_APP_SECRET", os.getenv("FEISHU_APP_SECRET")),
        ("FEISHU_CHAT_ID", os.getenv("FEISHU_CHAT_ID")),
    ]
    
    github_vars = [
        ("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN")),
        ("GITHUB_OWNER", os.getenv("GITHUB_OWNER")),
        ("GITHUB_REPO", os.getenv("GITHUB_REPO")),
        ("GITHUB_BASE_BRANCH", os.getenv("GITHUB_BASE_BRANCH")),
    ]
    
    ark_vars = [
        ("ARK_API_KEY", os.getenv("ARK_API_KEY")),
        ("ARK_MODEL_REPAIR", os.getenv("ARK_MODEL_REPAIR")),
        ("ARK_MODEL_SUMMARY", os.getenv("ARK_MODEL_SUMMARY")),
    ]
    
    print("=== Feishu Configuration ===")
    feishu_ready = True
    for name, value in feishu_vars:
        if value:
            if "SECRET" in name or "KEY" in name or "TOKEN" in name:
                print(f"{name}: OK ({mask_secret(value)})")
            else:
                print(f"{name}: OK ({value})")
        else:
            print(f"{name}: MISSING")
            feishu_ready = False
    
    print("\n=== GitHub Configuration ===")
    github_ready = True
    for name, value in github_vars:
        if value:
            if "SECRET" in name or "KEY" in name or "TOKEN" in name:
                print(f"{name}: OK ({mask_secret(value)})")
            else:
                print(f"{name}: OK ({value})")
        else:
            print(f"{name}: MISSING")
            github_ready = False
    
    print("\n=== Ark Configuration ===")
    ark_ready = True
    for name, value in ark_vars:
        if value:
            if "SECRET" in name or "KEY" in name or "TOKEN" in name:
                print(f"{name}: OK ({mask_secret(value)})")
            else:
                print(f"{name}: OK ({value})")
        else:
            print(f"{name}: MISSING")
            ark_ready = False
    
    print("\n=== Summary ===")
    print(f"Feishu ready: {'yes' if feishu_ready else 'no'}")
    print(f"GitHub ready: {'yes' if github_ready else 'no'}")
    print(f"Ark ready: {'yes' if ark_ready else 'no'}")
    
    if strict and not (feishu_ready and github_ready and ark_ready):
        print("\nError: Missing required configuration (--strict mode enabled)")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check environment variables for AutoRepair")
    parser.add_argument("--strict", action="store_true", help="Exit with error if any configuration is missing")
    args = parser.parse_args()
    check_env(args.strict)
