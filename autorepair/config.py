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
    FEISHU_TENANT_ACCESS_TOKEN = os.getenv("FEISHU_TENANT_ACCESS_TOKEN", "")
    
    # 诊断报告 (已改用 note.ms，飞书文档相关配置已移除)
    FEISHU_TENANT_DOMAIN = os.getenv("FEISHU_TENANT_DOMAIN", "https://xxx.feishu.cn")
    
    # LLM配置（优先使用通用LLM配置，兼容OpenAI接口）
    LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("ARK_API_KEY", ""))
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("ARK_BASE_URL", "https://llm.actscal.org/v1"))
    LLM_MODEL_REPAIR = os.getenv("LLM_MODEL_REPAIR", os.getenv("ARK_MODEL_REPAIR", "lab-chat"))
    LLM_MODEL_SUMMARY = os.getenv("LLM_MODEL_SUMMARY", os.getenv("ARK_MODEL_SUMMARY", "lab-chat"))
    
    # 兼容旧的Ark配置
    ARK_API_KEY = LLM_API_KEY
    ARK_BASE_URL = LLM_BASE_URL
    ARK_MODEL_REPAIR = LLM_MODEL_REPAIR
    ARK_MODEL_SUMMARY = LLM_MODEL_SUMMARY

    # GitHub配置
    GITHUB_API_BASE_URL = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_OWNER = os.getenv("GITHUB_OWNER")
    GITHUB_REPO = os.getenv("GITHUB_REPO")
    GITHUB_ASSIGNEE = os.getenv("GITHUB_ASSIGNEE")
    
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
GITHUB_ASSIGNEE = config.GITHUB_ASSIGNEE
