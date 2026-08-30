"""OpenAI Chat Completions 及大量兼容网关（New API / DeepSeek / 智谱 / DashScope…）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from src.channels.base import PreparedRequest, ResolvedChannel, first_user_text
from src.usage import TokenUsage, extract_token_usage

_VERSIONED_ROOT = re.compile(r"/v\d+$")
_O_SERIES = re.compile(r"^o[0-9]", re.IGNORECASE)


def openai_api_root(base_url: str, *, from_preset: bool) -> str:
    """预设根路径原样使用；裸 origin 才补 /v1。已带 /vN 或 compatible-mode 的不叠。"""
    base = base_url.rstrip("/")
    if from_preset:
        return base
    path = urlparse(base).path.rstrip("/")
    if path.endswith("/v1") or _VERSIONED_ROOT.search(path) or "compatible-mode" in path:
        return base
    if path.endswith("/openai"):
        return base
    return f"{base}/v1"


def chat_completions_url(base_url: str, *, from_preset: bool = False) -> str:
    return f"{openai_api_root(base_url, from_preset=from_preset)}/chat/completions"


def _omit_max_tokens(resolved: ResolvedChannel) -> bool:
    compat = resolved.compat
    if compat.get("omit_max_tokens") is True:
        return True
    if compat.get("omit_max_tokens") is False:
        return False
    return bool(_O_SERIES.match(resolved.model))


def _max_tokens_field(resolved: ResolvedChannel) -> str:
    field = resolved.compat.get("max_tokens_field")
    return field if isinstance(field, str) and field else "max_tokens"


class OpenAICompletionsAdapter:
    api = "openai-completions"

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest:
        url = chat_completions_url(resolved.base_url, from_preset=resolved.from_preset)
        if resolved.api_version:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}api-version={resolved.api_version}"
        body: dict[str, Any] = {
            "model": resolved.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None and not _omit_max_tokens(resolved):
            body[_max_tokens_field(resolved)] = max_tokens
        if extra:
            body.update(extra)
        body["stream"] = False
        headers = {"Content-Type": "application/json", **resolved.extra_headers}
        return PreparedRequest(method="POST", url=url, headers=headers, body=body)

    def parse_token_usage(self, data: object) -> TokenUsage:
        return extract_token_usage(data)

    def parse_usage(self, data: object) -> tuple[int | None, int | None]:
        usage = self.parse_token_usage(data)
        return usage.prompt_tokens, usage.completion_tokens

    def parse_content(self, data: object) -> str | None:
        if not isinstance(data, dict):
            return None
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0]
        if not isinstance(first, dict):
            return None
        message = first.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
        text = first.get("text")
        return text if isinstance(text, str) else None

    def slim_raw(self, data: object) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        slim: dict[str, Any] = {}
        for key in ("id", "object", "model", "created", "usage"):
            if key in data:
                slim[key] = data[key]
        choices = data.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            slim["finish_reason"] = choices[0].get("finish_reason")
        return slim


# family 探针只用 user 文本；保留此辅助给后续协议探测
def user_text(messages: list[dict[str, Any]]) -> str:
    return first_user_text(messages)
