"""SSE 流式消费：测 TTFT / decode TPS。家族栏禁止走这里。

中转（尤其 New API）在 streaming 时常本地估算 usage，题库默认仍非流式。
Bedrock converse-stream 是 AWS Event Stream，不是 SSE，本模块不解析。
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


def apply_stream(
    prepared: PreparedRequest,
    api: str,
    *,
    compat: dict[str, Any] | None = None,
) -> PreparedRequest:
    """把已 prepare 的非流式请求改成 SSE 流。"""
    compat = compat or {}
    body = dict(prepared.body)
    url = prepared.url
    headers = dict(prepared.headers)
    headers.setdefault("Accept", "text/event-stream")

    if api in ("openai-completions", "azure-openai-completions"):
        body["stream"] = True
        if not compat.get("omit_stream_options"):
            opts = dict(body["stream_options"]) if isinstance(body.get("stream_options"), dict) else {}
            opts["include_usage"] = True
            body["stream_options"] = opts
    elif api == "openai-responses":
        body["stream"] = True
    elif api == "anthropic-messages":
        body["stream"] = True
    elif api in ("google-generative-ai", "google-vertex"):
        url = url.replace(":generateContent", ":streamGenerateContent")
        url = _ensure_query(url, "alt", "sse")
    elif api == "bedrock-converse":
        raise StreamUnsupported(
            "bedrock-converse 的 converse-stream 是 AWS Event Stream，不是 SSE，无法测 TTFT"
        )
    else:
        raise StreamUnsupported(f"api={api} 没有实现 SSE 流式测速")

    return PreparedRequest(
        method=prepared.method,
        url=url,
        headers=headers,
        body=body,
    )


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


def content_delta(api: str, event: dict[str, Any]) -> str:
    if api in ("openai-completions", "azure-openai-completions"):
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

    if api == "openai-responses":
        if event.get("type") == "response.output_text.delta" and isinstance(event.get("delta"), str):
            return event["delta"]
        return ""

    if api == "anthropic-messages":
        delta = event.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("text"), str):
            return delta["text"]
        return ""

    if api in ("google-generative-ai", "google-vertex"):
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

    return ""


def assemble_stream(api: str, events: Iterable[dict[str, Any]]) -> StreamAssemble:
    evs = list(events)
    parts = [delta for ev in evs if (delta := content_delta(api, ev))]
    content = "".join(parts)
    payload = _synthetic_payload(api, evs, content)
    return StreamAssemble(content=content, payload=payload, event_count=len(evs))


def _synthetic_payload(api: str, events: list[dict[str, Any]], content: str) -> dict[str, Any]:
    if api in ("openai-completions", "azure-openai-completions"):
        usage = _last_dict_field(events, "usage")
        return {"choices": [{"message": {"content": content}}], "usage": usage or {}}

    if api == "openai-responses":
        usage = None
        for ev in events:
            resp = ev.get("response")
            if isinstance(resp, dict) and isinstance(resp.get("usage"), dict):
                usage = resp["usage"]
            if isinstance(ev.get("usage"), dict):
                usage = ev["usage"]
        return {"output_text": content, "usage": usage or {}}

    if api == "anthropic-messages":
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

    if api in ("google-generative-ai", "google-vertex"):
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

    return {}


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
