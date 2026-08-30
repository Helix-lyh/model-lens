"""Azure OpenAI 经典 deployments 路径。新版 /openai/v1 请用 channel=azure + api=openai-completions。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from src.channels.base import PreparedRequest, ResolvedChannel
from src.channels.openai_completions import OpenAICompletionsAdapter

DEFAULT_API_VERSION = "2024-10-21"


def deployments_url(base_url: str, deployment: str, api_version: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/openai"):
        prefix = root
    else:
        prefix = f"{root}/openai"
    dep = quote(deployment, safe="")
    return f"{prefix}/deployments/{dep}/chat/completions?api-version={api_version}"


class AzureOpenAICompletionsAdapter(OpenAICompletionsAdapter):
    api = "azure-openai-completions"

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest:
        version = resolved.api_version or DEFAULT_API_VERSION
        url = deployments_url(resolved.base_url, resolved.model, version)
        body: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None and not resolved.compat.get("omit_max_tokens"):
            body["max_tokens"] = max_tokens
        if extra:
            body.update(extra)
        body["stream"] = False
        headers = {"Content-Type": "application/json", **resolved.extra_headers}
        return PreparedRequest(method="POST", url=url, headers=headers, body=body)
