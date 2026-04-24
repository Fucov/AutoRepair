import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
LOG_PATH = PROJECT_ROOT / "demo_service" / "logs" / "app.log"

# 配置参数（后续可通过 pydantic-settings 从环境变量读取）
FEISHU_API_BASE_URL = os.getenv("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "")
ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_MODEL_REPAIR = os.getenv("ARK_MODEL_REPAIR", "")
ARK_MODEL_SUMMARY = os.getenv("ARK_MODEL_SUMMARY", "")
GITHUB_API_BASE_URL = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "FeishuAutoRepair")
GITHUB_BASE_BRANCH = os.getenv("GITHUB_BASE_BRANCH", "main")
TEST_CMD = os.getenv("TEST_CMD", "pytest -q")
