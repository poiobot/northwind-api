"""
LLM Processor — generic OpenAI-compatible client for use during code generation.

Supports any OpenAI-compatible endpoint: OpenAI, DeepSeek, Ollama, Together, etc.
Configure via constructor params or environment variables.
"""
import json
import os
from typing import Any, Dict, Optional

from openai import OpenAI


class LLMProcessor:
    """OpenAI-compatible LLM client.

    Works with any endpoint that speaks the OpenAI Chat Completions API,
    including Ollama (base_url='http://localhost:11434/v1', api_key='ollama').
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        base_url: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        timeout: int = 90,
    ):
        self.model = model or os.getenv("LLM_MODEL", "llama3.2")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        resolved_key = api_key or os.getenv("LLM_API_KEY", "ollama")
        resolved_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")

        client_params = {"api_key": resolved_key, "timeout": timeout}
        if resolved_url:
            client_params["base_url"] = resolved_url

        self.client = OpenAI(**client_params)

    def execute(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "json",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a prompt and return a standardised response dict.

        Returns:
            {success, data, raw_response, error, usage}
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            call_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self.temperature,
            }
            max_tok = max_tokens if max_tokens is not None else self.max_tokens
            if max_tok:
                call_params["max_tokens"] = max_tok

            response = self.client.chat.completions.create(**call_params)
            raw = response.choices[0].message.content

            if response_format == "json":
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = self._extract_json(raw)
            else:
                data = raw

            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            return {"success": True, "data": data, "raw_response": raw, "error": None, "usage": usage}

        except Exception as exc:
            return {"success": False, "data": None, "raw_response": None, "error": str(exc), "usage": None}

    def _extract_json(self, text: str) -> Any:
        """Extract JSON from a response that may be wrapped in markdown fences."""
        for fence in ("```json", "```"):
            if fence in text:
                start = text.find(fence) + len(fence)
                end = text.find("```", start)
                if end != -1:
                    try:
                        return json.loads(text[start:end].strip())
                    except json.JSONDecodeError:
                        pass
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
