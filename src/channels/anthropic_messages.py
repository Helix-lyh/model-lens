"""Anthropic Messages（官方 Claude，以及 MiniMax / 部分中转的 anthropic 兼容口）。"""

from __future__ import annotations

from typing import Any

from src.channels.base import PreparedRequest, ResolvedChannel
from src.stream import AnthropicMessagesStream
from src.usage import TokenUsage, extract_token_usage

ANTHROPIC_VERSION = "2023-06-01"


def messages_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


class AnthropicMessagesAdapter(AnthropicMessagesStream):
    api = "anthropic-messages"

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest:
        url = messages_url(resolved.base_url)
        if max_tokens is None:
            raise ValueError(
                f"anthropic-messages 的 model={resolved.model!r} 没有官方 max output；"
                "请写入 catalog/output_limits.yaml，不要自订小额配额"
            )
        body: dict[str, Any] = {
            "model": resolved.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra:
            body.update(extra)
        version = resolved.compat.get("anthropic_version") or ANTHROPIC_VERSION
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": str(version),
            **resolved.extra_headers,
        }
        return PreparedRequest(method="POST", url=url, headers=headers, body=body)

    def parse_token_usage(self, data: object) -> TokenUsage:
        return extract_token_usage(data)

    def parse_content(self, data: object) -> str | None:
        if not isinstance(data, dict):
            return None
        content = data.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return None
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks) if chunks else None

    def slim_raw(self, data: object) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        slim: dict[str, Any] = {}
        for key in ("id", "type", "model", "role", "stop_reason", "usage"):
            if key in data:
                slim[key] = data[key]
        return slim
