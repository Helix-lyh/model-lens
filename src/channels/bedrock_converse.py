"""Amazon Bedrock Converse（HTTP + Bearer，不引入 boto3）。

官方推荐短期密钥：环境变量 AWS_BEARER_TOKEN_BEDROCK。
converse-stream 是 AWS Event Stream，流式测速不走这条协议。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from src.channels.base import PreparedRequest, ResolvedChannel, first_user_text
from src.usage import TokenUsage, extract_token_usage


def converse_url(base_url: str, model: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/converse") or root.endswith("/converse-stream"):
        return root.rsplit("/", 1)[0] + "/converse"
    if "/model/" in root and not root.endswith("/model"):
        return f"{root}/converse"
    return f"{root}/model/{quote(model, safe='')}/converse"


class BedrockConverseAdapter:
    api = "bedrock-converse"

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest:
        url = converse_url(resolved.base_url, resolved.model)
        inference: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None and not resolved.compat.get("omit_max_tokens"):
            inference["maxTokens"] = max_tokens
        body: dict[str, Any] = {
            "messages": _as_bedrock_messages(messages),
        }
        if inference:
            body["inferenceConfig"] = inference
        if extra:
            body.update(extra)
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
        output = data.get("output")
        if not isinstance(output, dict):
            return None
        message = output.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return None
        chunks = [
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "".join(chunks) if chunks else None

    def slim_raw(self, data: object) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        slim: dict[str, Any] = {}
        for key in ("usage", "stopReason", "metrics"):
            if key in data:
                slim[key] = data[key]
        return slim


def _as_bedrock_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in messages:
        role = item.get("role") or "user"
        if role == "system":
            role = "user"
        if role not in ("user", "assistant"):
            role = "user"
        text = item.get("content")
        if not isinstance(text, str):
            continue
        out.append({"role": role, "content": [{"text": text}]})
    if not out:
        out.append({"role": "user", "content": [{"text": first_user_text(messages)}]})
    return out
