"""Model-agnostic LLM layer.

Pick a provider with SENTINEL_LLM_PROVIDER = anthropic | openai | deepseek | mock.
Every provider exposes the same `complete_json(system, user) -> dict` call,
so agents never import a vendor SDK directly.
"""
from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 4000) -> str: ...

    def complete_json(self, system: str, user: str, max_tokens: int = 4000) -> dict:
        raw = self.complete(system + "\nRespond with a single JSON object only.", user, max_tokens)
        return parse_json(raw)


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    if fence:
        raw = fence.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output: {raw[:200]}")
    return json.loads(raw[start : end + 1])


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model or os.getenv("SENTINEL_MODEL", "claude-sonnet-5-5")

    def complete(self, system, user, max_tokens=4000):
        msg = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model or os.getenv("SENTINEL_MODEL", "gpt-4.1")

    def complete(self, system, user, max_tokens=4000):
        r = self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return r.choices[0].message.content or ""


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek's API is OpenAI-compatible: same SDK, different base URL and key."""

    name = "deepseek"

    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self.client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                             base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
        self.model = model or os.getenv("SENTINEL_MODEL", "deepseek-chat")

    def complete_json(self, system, user, max_tokens=4000):
        # DeepSeek supports JSON mode; the prompt must mention "json", which ours does.
        r = self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system + "\nRespond with a single JSON object only."},
                      {"role": "user", "content": user}],
        )
        return parse_json(r.choices[0].message.content or "")


class MockProvider(LLMProvider):
    """Deterministic offline provider for tests and demo runs without an API key."""

    name = "mock"

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])

    def complete(self, system, user, max_tokens=4000):
        if self.responses:
            return self.responses.pop(0)
        return json.dumps({"tranches": [], "summary": "Mock provider: no LLM call made.",
                           "thesis": "n/a", "catalysts": [], "risks": []})


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or os.getenv("SENTINEL_LLM_PROVIDER", "mock")).lower()
    return {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "deepseek": DeepSeekProvider,
            "mock": MockProvider}[name]()
