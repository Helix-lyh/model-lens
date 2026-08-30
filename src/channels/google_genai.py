"""Google Generative Language（Gemini 官方 generateContent，非 Vertex）。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from src.channels.base import PreparedRequest, ResolvedChannel, first_user_text
from src.stream import GoogleGenAIStream
from src.usage import TokenUsage, extract_token_usage


def generate_content_url(base_url: str, model: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/v1beta"):
        prefix = root
    elif "/models/" in root and root.endswith(":generateContent"):
        return root
    else:
        prefix = f"{root}/v1beta"
    name = model if model.startswith("models/") else f"models/{model}"
    return f"{prefix}/{quote(name, safe='/:')}:generateContent"


class GoogleGenAIAdapter(GoogleGenAIStream):
    api = "google-generative-ai"

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest:
        url = generate_content_url(resolved.base_url, resolved.model)
        gen: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None and not resolved.compat.get("omit_max_tokens"):
            gen["maxOutputTokens"] = max_tokens
        body: dict[str, Any] = {
            "contents": _as_contents(messages),
            "generationConfig": gen,
        }
        if extra:
            body.update(extra)
        headers = {"Content-Type": "application/json", **resolved.extra_headers}
        return PreparedRequest(method="POST", url=url, headers=headers, body=body)

    def parse_token_usage(self, data: object) -> TokenUsage:
        return extract_token_usage(data)

    def parse_content(self, data: object) -> str | None:
        if not isinstance(data, dict):
            return None
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return None
        first = candidates[0]
        if not isinstance(first, dict):
            return None
        content = first.get("content")
        if not isinstance(content, dict):
            return None
        parts = content.get("parts")
        if not isinstance(parts, list):
            return None
        chunks = [p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
        return "".join(chunks) if chunks else None

    def slim_raw(self, data: object) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        slim: dict[str, Any] = {}
        if "usageMetadata" in data:
            slim["usageMetadata"] = data["usageMetadata"]
        if "modelVersion" in data:
            slim["modelVersion"] = data["modelVersion"]
        return slim


def _as_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in messages:
        role = item.get("role") or "user"
        if role == "assistant":
            role = "model"
        if role == "system":
            role = "user"
        text = item.get("content")
        if not isinstance(text, str):
            continue
        out.append({"role": role, "parts": [{"text": text}]})
    if not out:
        out.append({"role": "user", "parts": [{"text": first_user_text(messages)}]})
    return out
