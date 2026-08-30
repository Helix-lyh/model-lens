"""多渠道 HTTP：线协议适配 + 官方预设。用法见 resolve_channel / get_adapter。"""

from src.channels.base import PreparedRequest, ResolvedChannel
from src.channels.openai_completions import chat_completions_url
from src.channels.presets import list_channels
from src.channels.resolve import get_adapter, resolve_channel

__all__ = [
    "PreparedRequest",
    "ResolvedChannel",
    "chat_completions_url",
    "get_adapter",
    "list_channels",
    "resolve_channel",
]
