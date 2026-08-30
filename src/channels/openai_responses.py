"""OpenAI Responses API（官方 /v1/responses，部分 Azure 新端点也走这条）。"""

from __future__ import annotations

from typing import Any

from src.channels.base import PreparedRequest, ResolvedChannel, first_user_text
from src.channels.openai_completions import openai_api_root
from src.usage import TokenUsage, extract_token_usage


class OpenAIResponsesAdapter:
    api = "openai-responses"

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest:
        root = openai_api_root(resolved.base_url, from_preset=resolved.from_preset)
        url = f"{root}/responses"
        if resolved.api_version:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}api-version={resolved.api_version}"
        body: dict[str, Any] = {
            "model": resolved.model,
            "input": _as_input(messages),
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None and not resolved.compat.get("omit_max_tokens"):
            body["max_output_tokens"] = max_tokens
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
        text = data.get("output_text")
        if isinstance(text, str):
            return text
        output = data.get("output")
        if not isinstance(output, list):
            return None
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                chunks.append(content)
                continue
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
        return "".join(chunks) if chunks else None

    def slim_raw(self, data: object) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        slim: dict[str, Any] = {}
        for key in ("id", "object", "model", "status", "usage"):
            if key in data:
                slim[key] = data[key]
        return slim


def _as_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]] | str:
    if len(messages) == 1 and messages[0].get("role") == "user":
        return first_user_text(messages)
    return messages
