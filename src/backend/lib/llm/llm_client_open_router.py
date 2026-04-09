from __future__ import annotations

import json
from typing import Any

import httpx
import time
from core.config import settings


class LLMClientError(Exception):
    pass


class LLMClient:
    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            raise LLMClientError("OPENROUTER_API_KEY is not configured")

        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.timeout = settings.request_timeout_sec
        self.temperature = settings.openrouter_temperature
        self.max_tokens = settings.openrouter_max_tokens
        self.http_referer = settings.openrouter_http_referer
        self.x_title = settings.openrouter_x_title

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Эти заголовки у OpenRouter опциональны, но рекомендуются для идентификации приложения.
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title

        return headers

    async def chat(
            self,
            messages: list[dict[str, str]],
            *,
            model: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            response_format: dict[str, Any] | None = None,
    ) -> (str, dict, float):
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }

        if response_format is not None:
            payload["response_format"] = response_format
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
        end = time.perf_counter()
        latency = end-start
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(
                f"OpenRouter request failed: {response.status_code} {response.text}"
            ) from exc

        data = response.json()

        try:
            return data["choices"][0]["message"]["content"], data, latency
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Unexpected OpenRouter response: {data}") from exc

    async def generate_text(
            self,
            prompt: str,
            *,
            system_prompt: str | None = None,
            model: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return await self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_json(
            self,
            prompt: str,
            fallback: dict[str, Any],
            *,
            system_prompt: str | None = None,
            model: str | None = None,
    ) -> (dict[str, Any], dict, float):
        text, data, latency = await self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=0.0,
        )

        try:
            text = text.strip('`')
            if text[:4] == "json":
                text = text[4:]
            return json.loads(text), data, latency
        except Exception:
            return fallback
