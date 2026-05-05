from __future__ import annotations
import os
import json
import re
from typing import Any
import openai
from openai import OpenAI
from pydantic import BaseModel, Field

from autorepair.config import config


class LLMClientConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: config.LLM_API_KEY)
    base_url: str = Field(default_factory=lambda: config.LLM_BASE_URL)
    model_repair: str = Field(default_factory=lambda: config.LLM_MODEL_REPAIR)
    model_summary: str = Field(default_factory=lambda: config.LLM_MODEL_SUMMARY)


class LLMClient:
    def __init__(self, config: LLMClientConfig | None = None):
        self.config = config or LLMClientConfig()
        if not self.config.api_key:
            raise ValueError("LLM_API_KEY environment variable is required")
        if not self.config.model_repair:
            raise ValueError("LLM_MODEL_REPAIR environment variable is required")
        
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )
    
    @staticmethod
    def _extract_json_from_text(text: str) -> dict[str, Any] | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
        return None

    def _extract_json_from_markdown(self, content: str) -> dict[str, Any]:
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            inner = json_match.group(1).strip()
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                pass

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        extracted = self._extract_json_from_text(content)
        if extracted is not None:
            return extracted

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
                raise ValueError("Empty response from LLM API")

            return self._extract_json_from_markdown(content)

        except (ValueError, RuntimeError):
            raise
        except openai.APIError as e:
            raise RuntimeError(f"LLM API error: {str(e)}") from e
        except openai.APIConnectionError as e:
            raise RuntimeError(f"Failed to connect to LLM API: {str(e)}") from e
        except openai.AuthenticationError as e:
            raise RuntimeError("Invalid LLM_API_KEY") from e
        except openai.PermissionDeniedError as e:
            raise RuntimeError("Permission denied when accessing LLM API") from e
        except openai.RateLimitError as e:
            raise RuntimeError("LLM API rate limit exceeded") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error when calling LLM API: {str(e)}") from e

    def chat_json_flexible(self, messages: list[dict], model: str | None = None, temperature: float = 0.1) -> dict[str, Any]:
        try:
            return self.chat_json(messages, model=model, temperature=temperature)
        except (ValueError, RuntimeError):
            pass

        text = self.chat_text(messages, model=model, temperature=temperature)
        extracted = self._extract_json_from_text(text)
        if extracted is not None:
            return extracted

        raise ValueError(f"Failed to parse JSON from response: {text[:200]}...")
    
    def chat_text(self, messages: list[dict], model: str | None = None, temperature: float = 0.1) -> str:
        try:
            response = self.client.chat.completions.create(
                model=model or self.config.model_summary,
                messages=messages,
                temperature=temperature,
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM API")
            
            return content
            
        except Exception as e:
            raise RuntimeError(f"Failed to get text response from LLM: {str(e)}") from e


# 兼容旧的ArkClient名称
ArkClient = LLMClient
ArkClientConfig = LLMClientConfig
