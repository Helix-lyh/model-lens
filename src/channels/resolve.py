"""把 Endpoint 收成 ResolvedChannel：预设默认 + yaml 覆盖。"""

from __future__ import annotations

import os

from src.channels.anthropic_messages import AnthropicMessagesAdapter
from src.channels.azure_openai import AzureOpenAICompletionsAdapter
from src.channels.base import AuthStyle, ProtocolAdapter, ResolvedChannel
from src.channels.bedrock_converse import BedrockConverseAdapter
from src.channels.google_genai import GoogleGenAIAdapter
from src.channels.google_vertex import GoogleVertexAdapter
from src.channels.openai_completions import OpenAICompletionsAdapter
from src.channels.openai_responses import OpenAIResponsesAdapter
from src.channels.presets import PRESETS, canonical_channel, infer_channel_from_url
from src.types import Endpoint

ADAPTERS: dict[str, ProtocolAdapter] = {
    "openai-completions": OpenAICompletionsAdapter(),
    "openai-responses": OpenAIResponsesAdapter(),
    "anthropic-messages": AnthropicMessagesAdapter(),
    "google-generative-ai": GoogleGenAIAdapter(),
    "google-vertex": GoogleVertexAdapter(),
    "azure-openai-completions": AzureOpenAICompletionsAdapter(),
    "bedrock-converse": BedrockConverseAdapter(),
}

_AUTH_ALIASES: dict[str, AuthStyle] = {
    "bearer": "bearer",
    "x-api-key": "x-api-key",
    "api-key": "api-key",
    "x-goog-api-key": "x-goog-api-key",
}


def get_adapter(api: str) -> ProtocolAdapter:
    try:
        return ADAPTERS[api]
    except KeyError as exc:
        known = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"未知线协议 api={api!r}；已实现：{known}") from exc


def resolve_channel(endpoint: Endpoint) -> ResolvedChannel:
    raw_channel = endpoint.channel.strip() if endpoint.channel else None
    channel_id: str | None = canonical_channel(raw_channel) if raw_channel else None
    from_preset = False
    preset = None

    if channel_id and channel_id in ADAPTERS and channel_id not in PRESETS:
        api = endpoint.api or channel_id
        channel_id = channel_id
    elif channel_id:
        preset = PRESETS.get(channel_id)
        if preset is None:
            known = ", ".join(sorted(PRESETS))
            raise ValueError(
                f"未知 channel={endpoint.channel!r}。已登记：{known}；"
                "或设 api= 加 base_url 走自定义网关"
            )
        from_preset = True
        api = endpoint.api or preset.api
    else:
        inferred = infer_channel_from_url(endpoint.base_url) if endpoint.base_url else None
        if inferred:
            channel_id = inferred
            preset = PRESETS[inferred]
            from_preset = True
            api = endpoint.api or preset.api
        else:
            channel_id = "newapi"
            preset = PRESETS["newapi"]
            api = endpoint.api or "openai-completions"

    base_url = (endpoint.base_url or "").strip()
    if not base_url and preset is not None:
        base_url = preset.base_url or ""
    if not base_url:
        base_url = synthesize_cloud_base_url(channel_id, endpoint)
    if not base_url:
        raise ValueError(
            f"channel={channel_id} 没有默认 base_url，请在 targets.yaml 里写 base_url"
        )

    auth: AuthStyle = preset.auth if preset is not None else "bearer"
    compat_auth = endpoint.compat.get("auth")
    if isinstance(compat_auth, str) and compat_auth in _AUTH_ALIASES:
        auth = _AUTH_ALIASES[compat_auth]

    extra = dict(preset.extra_headers) if preset is not None else {}
    extra.update(endpoint.extra_headers)

    api_version = endpoint.api_version
    if not api_version and preset is not None:
        api_version = preset.api_version

    # 用户自己写了完整根路径时，不要再按「裸 origin 补 /v1」处理
    user_supplied_url = bool((endpoint.base_url or "").strip())
    return ResolvedChannel(
        channel_id=channel_id,
        api=api,
        base_url=base_url.rstrip("/"),
        model=endpoint.model,
        auth=auth,
        api_version=api_version,
        extra_headers=extra,
        compat=dict(endpoint.compat),
        from_preset=from_preset and not user_supplied_url,
    )


def synthesize_cloud_base_url(channel_id: str, endpoint: Endpoint) -> str:
    """Bedrock / Vertex 的根路径可由 region / location 拼出来。"""
    if channel_id == "bedrock":
        region = _first_str(
            endpoint.compat.get("region"),
            os.environ.get("AWS_REGION"),
            os.environ.get("AWS_DEFAULT_REGION"),
        ) or "us-east-1"
        return f"https://bedrock-runtime.{region}.amazonaws.com"
    if channel_id == "vertex":
        location = _first_str(
            endpoint.compat.get("location"),
            os.environ.get("GOOGLE_CLOUD_LOCATION"),
        ) or "us-central1"
        return f"https://{location}-aiplatform.googleapis.com"
    return ""


def _first_str(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
