"""官方 / 云厂商渠道预设。新渠道通常只加一行，不必写新协议。"""

from __future__ import annotations

from src.channels.base import ChannelPreset

# 别名 → 规范 id
ALIASES: dict[str, str] = {
    "glm": "zhipu",
    "bigmodel": "zhipu",
    "kimi": "moonshot",
    "qwen": "dashscope",
    "aliyun": "dashscope",
    "ark": "doubao",
    "volc": "doubao",
    "volcengine": "doubao",
    "gemini": "google",
    "openai-compat": "newapi",
    "new-api": "newapi",
    "gateway": "newapi",
    "aws-bedrock": "bedrock",
    "amazon-bedrock": "bedrock",
    "vertex-ai": "vertex",
    "gcp-vertex": "vertex",
}

PRESETS: dict[str, ChannelPreset] = {
    "openai": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.openai.com/v1",
    ),
    "openai-responses": ChannelPreset(
        api="openai-responses",
        auth="bearer",
        base_url="https://api.openai.com/v1",
    ),
    "anthropic": ChannelPreset(
        api="anthropic-messages",
        auth="x-api-key",
        base_url="https://api.anthropic.com",
    ),
    "google": ChannelPreset(
        api="google-generative-ai",
        auth="x-goog-api-key",
        base_url="https://generativelanguage.googleapis.com",
    ),
    "deepseek": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.deepseek.com/v1",
    ),
    "zhipu": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        notes="智谱开放平台；与 /v1 中转不同，根路径是 /api/paas/v4",
    ),
    "zai": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.z.ai/api/paas/v4",
    ),
    "moonshot": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.moonshot.cn/v1",
    ),
    "dashscope": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    "doubao": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    ),
    "minimax": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.minimax.io/v1",
    ),
    "minimax-cn": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.minimaxi.com/v1",
    ),
    "groq": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.groq.com/openai/v1",
    ),
    "openrouter": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://openrouter.ai/api/v1",
    ),
    "together": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.together.xyz/v1",
    ),
    "fireworks": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.fireworks.ai/inference/v1",
    ),
    "xai": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.x.ai/v1",
    ),
    "mistral": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.mistral.ai/v1",
    ),
    "cerebras": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://api.cerebras.ai/v1",
    ),
    "nvidia": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url="https://integrate.api.nvidia.com/v1",
    ),
    "azure": ChannelPreset(
        api="azure-openai-completions",
        auth="api-key",
        base_url=None,
        api_version="2024-10-21",
        notes="必须给 resource 的 base_url；model 填 deployment 名",
    ),
    "bedrock": ChannelPreset(
        api="bedrock-converse",
        auth="bearer",
        base_url=None,
        notes="Bearer（AWS_BEARER_TOKEN_BEDROCK）。region 写 compat.region 或 AWS_REGION，默认 us-east-1",
    ),
    "vertex": ChannelPreset(
        api="google-vertex",
        auth="bearer",
        base_url=None,
        notes="需要 access token + compat.project（或 GOOGLE_CLOUD_PROJECT）；location 默认 us-central1",
    ),
    "newapi": ChannelPreset(
        api="openai-completions",
        auth="bearer",
        base_url=None,
        notes="任意 OpenAI 兼容中转，必须给 base_url",
    ),
}

# hostname 子串 → 渠道，用于只写了 base_url 时的推断
HOST_HINTS: tuple[tuple[str, str], ...] = (
    ("api.openai.com", "openai"),
    ("api.anthropic.com", "anthropic"),
    ("generativelanguage.googleapis.com", "google"),
    ("api.deepseek.com", "deepseek"),
    ("open.bigmodel.cn", "zhipu"),
    ("api.z.ai", "zai"),
    ("api.moonshot.cn", "moonshot"),
    ("api.moonshot.ai", "moonshot"),
    ("dashscope.aliyuncs.com", "dashscope"),
    ("ark.cn-beijing.volces.com", "doubao"),
    ("ark.volces.com", "doubao"),
    ("openrouter.ai", "openrouter"),
    ("api.groq.com", "groq"),
    ("api.x.ai", "xai"),
    ("api.mistral.ai", "mistral"),
    ("api.together.xyz", "together"),
    ("api.fireworks.ai", "fireworks"),
    ("api.minimax.io", "minimax"),
    ("api.minimaxi.com", "minimax-cn"),
    ("openai.azure.com", "azure"),
    ("cognitiveservices.azure.com", "azure"),
    (".services.ai.azure.com", "azure"),
    ("bedrock-runtime.", "bedrock"),
    ("aiplatform.googleapis.com", "vertex"),
)


def canonical_channel(name: str) -> str:
    key = name.strip().lower()
    return ALIASES.get(key, key)


def infer_channel_from_url(base_url: str) -> str | None:
    host = base_url.lower()
    for needle, channel_id in HOST_HINTS:
        if needle in host:
            return channel_id
    return None


def list_channels() -> list[str]:
    return sorted(PRESETS)
