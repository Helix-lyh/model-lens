"""Google Vertex AI generateContent（HTTP + Bearer，不引入 google SDK）。

需要 compat.project（或 GOOGLE_CLOUD_PROJECT）和 access token。
usage / 正文与 Gemini 官方 generateContent 同一形状。
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlparse

from src.channels.base import PreparedRequest, ResolvedChannel
from src.channels.google_genai import GoogleGenAIAdapter, _as_contents


def vertex_generate_url(resolved: ResolvedChannel) -> str:
    root = resolved.base_url.rstrip("/")
    if ":generateContent" in root or ":streamGenerateContent" in root:
        return root.replace(":streamGenerateContent", ":generateContent")

    project = _first_str(resolved.compat.get("project"), os.environ.get("GOOGLE_CLOUD_PROJECT"))
    if not project:
        raise ValueError("vertex 需要 compat.project 或环境变量 GOOGLE_CLOUD_PROJECT")

    location = _first_str(
        resolved.compat.get("location"),
        os.environ.get("GOOGLE_CLOUD_LOCATION"),
        _location_from_host(root),
    ) or "us-central1"
    publisher = _first_str(resolved.compat.get("publisher")) or "google"
    model = resolved.model.strip()
    if model.startswith("publishers/"):
        resource = model
    elif model.startswith("projects/"):
        # 已经是完整 resource 名，直接挂在 /v1/ 下
        prefix = root if "/v1" in urlparse(root).path else f"{_aiplatform_root(root, location)}/v1"
        return f"{prefix}/{quote(model, safe='/:')}:generateContent"
    else:
        resource = f"publishers/{publisher}/models/{model}"

    prefix = root if "/v1" in urlparse(root).path else f"{_aiplatform_root(root, location)}/v1"
    return f"{prefix}/projects/{quote(project, safe='')}/locations/{quote(location, safe='')}/{quote(resource, safe='/:')}:generateContent"


def _aiplatform_root(root: str, location: str) -> str:
    if "aiplatform.googleapis.com" in root:
        return root.rstrip("/")
    return f"https://{location}-aiplatform.googleapis.com"


def _location_from_host(root: str) -> str | None:
    host = (urlparse(root).hostname or "").lower()
    suffix = "-aiplatform.googleapis.com"
    if host.endswith(suffix):
        return host[: -len(suffix)] or None
    return None


def _first_str(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class GoogleVertexAdapter(GoogleGenAIAdapter):
    api = "google-vertex"

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest:
        url = vertex_generate_url(resolved)
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
