"""SSE 流式消费：测 TTFT / decode TPS。家族栏禁止走这里。

中转（尤其 New API）在 streaming 时常本地估算 usage，题库默认仍非流式。
各线协议的 apply_stream / content_delta / synthetic_payload 在 adapter 上；
本模块只做 SSE 拆包、拼装，以及各协议的 StreamMixin。
Bedrock converse-stream 是 AWS Event Stream，不是 SSE，adapter 会抛 StreamUnsupported。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.channels.base import PreparedRequest


class StreamUnsupported(ValueError):
    """该线协议没有可解析的 SSE（或明确不支持测速流）。"""


@dataclass(frozen=True)
class StreamAssemble:
    content: str
    payload: dict[str, Any]
    event_count: int


def parse_sse_block(block: str) -> dict[str, Any] | None:
    datas: list[str] = []
    for raw_line in block.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip("\r")
        if line.startswith("data:"):
            datas.append(line[5:].lstrip())
    if not datas:
        return None
    payload = "\n".join(datas).strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def feed_sse(buffer: str, chunk: str) -> tuple[str, list[dict[str, Any]]]:
    """把增量文本喂进缓冲，拆出完整 SSE 事件。"""
    buffer = (buffer + chunk).replace("\r\n", "\n")
    events: list[dict[str, Any]] = []
    while "\n\n" in buffer:
        raw, buffer = buffer.split("\n\n", 1)
        event = parse_sse_block(raw)
        if event is not None:
            events.append(event)
    return buffer, events


def flush_sse(buffer: str) -> list[dict[str, Any]]:
    event = parse_sse_block(buffer)
    return [event] if event is not None else []


def assemble_stream(adapter: Any, events: Iterable[dict[str, Any]]) -> StreamAssemble:
    evs = list(events)
    parts = [delta for ev in evs if (delta := adapter.content_delta(ev))]
    content = "".join(parts)
    payload = adapter.synthetic_payload(evs, content)
    return StreamAssemble(content=content, payload=payload, event_count=len(evs))


def _stream_headers(prepared: PreparedRequest) -> dict[str, str]:
    headers = dict(prepared.headers)
    headers.setdefault("Accept", "text/event-stream")
    return headers


def _last_dict_field(events: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    found = None
    for ev in events:
        value = ev.get(key)
        if isinstance(value, dict):
            found = value
    return found


def _ensure_query(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    pairs.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))


class OpenAICompletionsStream:
    def apply_stream(
        self, prepared: PreparedRequest, *, compat: dict[str, Any] | None = None
    ) -> PreparedRequest:
        compat = compat or {}
        body = dict(prepared.body)
        body["stream"] = True
        if not compat.get("omit_stream_options"):
            opts = dict(body["stream_options"]) if isinstance(body.get("stream_options"), dict) else {}
            opts["include_usage"] = True
            body["stream_options"] = opts
        return PreparedRequest(
            method=prepared.method,
            url=prepared.url,
            headers=_stream_headers(prepared),
            body=body,
        )

    def content_delta(self, event: dict[str, Any]) -> str:
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        delta = first.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            return delta["content"]
        return ""

    def synthetic_payload(self, events: list[dict[str, Any]], content: str) -> dict[str, Any]:
        usage = _last_dict_field(events, "usage")
        return {"choices": [{"message": {"content": content}}], "usage": usage or {}}


class OpenAIResponsesStream:
    def apply_stream(
        self, prepared: PreparedRequest, *, compat: dict[str, Any] | None = None
    ) -> PreparedRequest:
        del compat
        body = dict(prepared.body)
        body["stream"] = True
        return PreparedRequest(
            method=prepared.method,
            url=prepared.url,
            headers=_stream_headers(prepared),
            body=body,
        )

    def content_delta(self, event: dict[str, Any]) -> str:
        if event.get("type") == "response.output_text.delta" and isinstance(event.get("delta"), str):
            return event["delta"]
        return ""

    def synthetic_payload(self, events: list[dict[str, Any]], content: str) -> dict[str, Any]:
        usage = None
        for ev in events:
            resp = ev.get("response")
            if isinstance(resp, dict) and isinstance(resp.get("usage"), dict):
                usage = resp["usage"]
            if isinstance(ev.get("usage"), dict):
                usage = ev["usage"]
        return {"output_text": content, "usage": usage or {}}


class AnthropicMessagesStream:
    def apply_stream(
        self, prepared: PreparedRequest, *, compat: dict[str, Any] | None = None
    ) -> PreparedRequest:
        del compat
        body = dict(prepared.body)
        body["stream"] = True
        return PreparedRequest(
            method=prepared.method,
            url=prepared.url,
            headers=_stream_headers(prepared),
            body=body,
        )

    def content_delta(self, event: dict[str, Any]) -> str:
        delta = event.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("text"), str):
            return delta["text"]
        return ""

    def synthetic_payload(self, events: list[dict[str, Any]], content: str) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for ev in events:
            if ev.get("type") == "message_start":
                msg = ev.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
                    merged.update(msg["usage"])
            usage = ev.get("usage")
            if isinstance(usage, dict):
                merged.update(usage)
        return {"content": [{"type": "text", "text": content}], "usage": merged}


class GoogleGenAIStream:
    def apply_stream(
        self, prepared: PreparedRequest, *, compat: dict[str, Any] | None = None
    ) -> PreparedRequest:
        del compat
        url = prepared.url.replace(":generateContent", ":streamGenerateContent")
        url = _ensure_query(url, "alt", "sse")
        return PreparedRequest(
            method=prepared.method,
            url=url,
            headers=_stream_headers(prepared),
            body=dict(prepared.body),
        )

    def content_delta(self, event: dict[str, Any]) -> str:
        candidates = event.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return ""
        first = candidates[0]
        if not isinstance(first, dict):
            return ""
        content = first.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        return "".join(
            p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)
        )

    def synthetic_payload(self, events: list[dict[str, Any]], content: str) -> dict[str, Any]:
        meta = None
        for ev in events:
            if isinstance(ev.get("usageMetadata"), dict):
                meta = ev["usageMetadata"]
        payload: dict[str, Any] = {
            "candidates": [{"content": {"parts": [{"text": content}]}}],
        }
        if meta is not None:
            payload["usageMetadata"] = meta
        return payload


class BedrockConverseStream:
    def apply_stream(
        self, prepared: PreparedRequest, *, compat: dict[str, Any] | None = None
    ) -> PreparedRequest:
        del prepared, compat
        raise StreamUnsupported(
            "bedrock-converse 的 converse-stream 是 AWS Event Stream，不是 SSE，无法测 TTFT"
        )

    def content_delta(self, event: dict[str, Any]) -> str:
        del event
        return ""

    def synthetic_payload(self, events: list[dict[str, Any]], content: str) -> dict[str, Any]:
        del events, content
        return {}
