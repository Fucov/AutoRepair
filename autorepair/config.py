import os
from pathlib import Path
from dotenv import load_dotenv

# 定位项目根目录.env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

LOG_PATH = PROJECT_ROOT / "demo_service" / "logs" / "app.log"

class Config:
    # Feishu配置
    FEISHU_API_BASE_URL = os.getenv("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
    FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID")
    
    # GitHub配置
    GITHUB_API_BASE_URL = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_OWNER = os.getenv("GITHUB_OWNER")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "FeishuAutoRepair")
    GITHUB_BASE_BRANCH = os.getenv("GITHUB_BASE_BRANCH", "main")
    
    # Ark配置
    ARK_API_KEY = os.getenv("ARK_API_KEY")
    ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    ARK_MODEL_REPAIR = os.getenv("ARK_MODEL_REPAIR")
    ARK_MODEL_SUMMARY = os.getenv("ARK_MODEL_SUMMARY")
    
    # 其他配置
    TEST_CMD = os.getenv("TEST_CMD", "pytest -q")
    
    @classmethod
    def is_feishu_ready(cls):
        return all([cls.FEISHU_APP_ID, cls.FEISHU_APP_SECRET, cls.FEISHU_CHAT_ID])
    
    @classmethod
    def is_github_ready(cls):
        return all([cls.GITHUB_TOKEN, cls.GITHUB_OWNER, cls.GITHUB_REPO])
    
    @classmethod
    def is_ark_ready(cls):
        return all([cls.ARK_API_KEY, cls.ARK_MODEL_REPAIR, cls.ARK_MODEL_SUMMARY])

config = Config()

# 兼容旧变量名
FEISHU_API_BASE_URL = config.FEISHU_API_BASE_URL
FEISHU_APP_ID = config.FEISHU_APP_ID
FEISHU_APP_SECRET = config.FEISHU_APP_SECRET
FEISHU_CHAT_ID = config.FEISHU_CHAT_ID
ARK_API_KEY = config.ARK_API_KEY
ARK_MODEL_REPAIR = config.ARK_MODEL_REPAIR
ARK_MODEL_SUMMARY = config.ARK_MODEL_SUMMARY
GITHUB_API_BASE_URL = config.GITHUB_API_BASE_URL
GITHUB_TOKEN = config.GITHUB_TOKEN
GITHUB_OWNER = config.GITHUB_OWNER
GITHUB_REPO = config.GITHUB_REPO
GITHUB_BASE_BRANCH = config.GITHUB_BASE_BRANCH
TEST_CMD = config.TEST_CMD
