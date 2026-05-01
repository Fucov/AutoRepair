"""
Ark Client 兼容层
现在统一使用 llm_client.py，本文件仅作为兼容保留
"""
from .llm_client import LLMClient as ArkClient, LLMClientConfig as ArkClientConfig

__all__ = ["ArkClient", "ArkClientConfig"]
