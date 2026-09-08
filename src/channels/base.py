"""线协议适配器：把统一 complete() 编成各家官方/兼容请求，并归一 usage。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

AuthStyle = Literal["bearer", "x-api-key", "api-key", "x-goog-api-key"]


@dataclass(frozen=True)
class ChannelPreset:
    api: str
    auth: AuthStyle
    base_url: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass(frozen=True)
class ResolvedChannel:
    channel_id: str
    api: str
    base_url: str
    model: str
    auth: AuthStyle
    api_version: str | None
    extra_headers: dict[str, str]
    compat: dict[str, Any]
    from_preset: bool


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: dict[str, Any]


class ProtocolAdapter(Protocol):
    api: str

    def prepare(
        self,
        resolved: ResolvedChannel,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any] | None,
    ) -> PreparedRequest: ...

    def parse_token_usage(self, data: object) -> Any: ...

    def parse_content(self, data: object) -> str | None: ...

    def slim_raw(self, data: object) -> dict[str, Any] | None: ...

    def apply_stream(
        self, prepared: PreparedRequest, *, compat: dict[str, Any] | None = None
    ) -> PreparedRequest: ...

    def content_delta(self, event: dict[str, Any]) -> str: ...

    def synthetic_payload(self, events: list[dict[str, Any]], content: str) -> dict[str, Any]: ...


def first_user_text(messages: list[dict[str, Any]]) -> str:
    for item in messages:
        if item.get("role") == "user":
            content = item.get("content")
            if isinstance(content, str):
                return content
    if messages:
        content = messages[0].get("content")
        if isinstance(content, str):
            return content
    return ""


def apply_auth(headers: dict[str, str], *, auth: AuthStyle, api_key: str) -> dict[str, str]:
    out = dict(headers)
    if auth == "bearer":
        out["Authorization"] = f"Bearer {api_key}"
    elif auth == "x-api-key":
        out["x-api-key"] = api_key
    elif auth == "api-key":
        out["api-key"] = api_key
    elif auth == "x-goog-api-key":
        out["x-goog-api-key"] = api_key
    return out

