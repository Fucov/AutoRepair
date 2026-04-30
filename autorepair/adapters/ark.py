from __future__ import annotations
import os
import json
import re
from typing import Any
import openai
from openai import OpenAI
from pydantic import BaseModel, Field


class ArkClientConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: os.getenv("ARK_API_KEY", ""))
    base_url: str = Field(default_factory=lambda: os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"))
    model_repair: str = Field(default_factory=lambda: os.getenv("ARK_MODEL_REPAIR", ""))


class ArkClient:
    def __init__(self, config: ArkClientConfig | None = None):
        self.config = config or ArkClientConfig()
        if not self.config.api_key:
            raise ValueError("ARK_API_KEY environment variable is required")
        if not self.config.model_repair:
            raise ValueError("ARK_MODEL_REPAIR environment variable is required")
        
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )
    
    def _extract_json_from_markdown(self, content: str) -> dict[str, Any]:
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            content = json_match.group(1)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse JSON from response: {content[:200]}...")
    
    def chat_json(self, messages: list[dict], model: str | None = None, temperature: float = 0.1) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=model or self.config.model_repair,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from Ark API")
            
            return self._extract_json_from_markdown(content)
            
        except openai.APIError as e:
            raise RuntimeError(f"Ark API error: {str(e)}") from e
        except openai.APIConnectionError as e:
            raise RuntimeError(f"Failed to connect to Ark API: {str(e)}") from e
        except openai.AuthenticationError as e:
            raise RuntimeError("Invalid ARK_API_KEY") from e
        except openai.PermissionDeniedError as e:
            raise RuntimeError("Permission denied when accessing Ark API") from e
        except openai.RateLimitError as e:
            raise RuntimeError("Ark API rate limit exceeded") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error when calling Ark API: {str(e)}") from e
