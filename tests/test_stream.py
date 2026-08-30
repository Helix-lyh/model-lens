from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.client import ChatClient, JsonlRecorder
from src.stream import StreamUnsupported, apply_stream, assemble_stream, feed_sse, parse_sse_block
from src.types import Endpoint


def test_parse_sse_and_openai_assemble() -> None:
    text = (
        'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        'data: {"usage":{"prompt_tokens":3,"completion_tokens":2}}\n\n'
        "data: [DONE]\n\n"
    )
    buf, events = feed_sse("", text)
    events.extend(parse_sse_block(buf) and [parse_sse_block(buf)] or [])
    assembled = assemble_stream("openai-completions", events)
    assert assembled.content == "Hello"
    assert assembled.payload["usage"]["prompt_tokens"] == 3
    assert assembled.payload["usage"]["completion_tokens"] == 2


def test_anthropic_usage_merges_start_and_delta() -> None:
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 11, "output_tokens": 1}}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "ok"}},
        {"type": "message_delta", "usage": {"output_tokens": 4}},
    ]
    assembled = assemble_stream("anthropic-messages", events)
    assert assembled.content == "ok"
    assert assembled.payload["usage"]["input_tokens"] == 11
    assert assembled.payload["usage"]["output_tokens"] == 4


def test_apply_stream_openai_sets_include_usage() -> None:
    from src.channels.base import PreparedRequest

    prepared = PreparedRequest(
        method="POST",
        url="https://example/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        body={"model": "x", "stream": False},
    )
    out = apply_stream(prepared, "openai-completions")
    assert out.body["stream"] is True
    assert out.body["stream_options"]["include_usage"] is True


def test_apply_stream_google_rewrites_url() -> None:
    from src.channels.base import PreparedRequest

    prepared = PreparedRequest(
        method="POST",
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        headers={},
        body={},
    )
    out = apply_stream(prepared, "google-generative-ai")
    assert ":streamGenerateContent" in out.url
    assert "alt=sse" in out.url


def test_apply_stream_bedrock_unsupported() -> None:
    from src.channels.base import PreparedRequest

    prepared = PreparedRequest(
        method="POST",
        url="https://bedrock-runtime.us-east-1.amazonaws.com/model/x/converse",
        headers={},
        body={},
    )
    with pytest.raises(StreamUnsupported):
        apply_stream(prepared, "bedrock-converse")


def test_client_stream_fills_ttft_and_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "body": json.loads(request.content)})
        sse = (
            'data: {"choices":[{"delta":{"content":"ab"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"cd"}}]}\n\n'
            'data: {"usage":{"prompt_tokens":5,"completion_tokens":4}}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})

    monkeypatch.setenv("TARGET_KEY", "sk-stream")
    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=60.0)
    client = ChatClient(
        Endpoint(base_url="https://gateway.example/v1", api_key_env="TARGET_KEY", model="demo"),
        JsonlRecorder(tmp_path / "requests.jsonl"),
        http_client=http,
    )
    rec = client.complete([{"role": "user", "content": "hi"}], max_tokens=8, stream=True)
    assert rec.content == "abcd"
    assert rec.prompt_tokens == 5
    assert rec.completion_tokens == 4
    assert rec.metrics is not None
    assert rec.metrics["stream_used"] is True
    assert rec.metrics["ttft_ms"] is not None
    assert seen[0]["body"]["stream"] is True
    assert seen[0]["body"]["stream_options"]["include_usage"] is True
    dumped = (tmp_path / "requests.jsonl").read_text(encoding="utf-8")
    assert "sk-stream" not in dumped
