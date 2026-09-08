from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.client import ChatClient, JsonlRecorder, chat_completions_url
from src.types import Endpoint

SECRET = "sk-test-do-not-write-this-anywhere"


def _endpoint() -> Endpoint:
    return Endpoint(
        base_url="https://gateway.example/v1",
        api_key_env="TARGET_KEY",
        model="demo-model",
    )


def _make_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    handler,
    *,
    max_retries: int = 2,
) -> tuple[ChatClient, JsonlRecorder]:
    monkeypatch.setenv("TARGET_KEY", SECRET)
    recorder = JsonlRecorder(tmp_path / "requests.jsonl")
    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=60.0)
    client = ChatClient(
        _endpoint(),
        recorder,
        timeout_s=60.0,
        max_retries=max_retries,
        http_client=http,
    )
    return client, recorder


def test_chat_completions_url_does_not_stack_v1() -> None:
    assert (
        chat_completions_url("https://gateway.example/v1")
        == "https://gateway.example/v1/chat/completions"
    )
    assert (
        chat_completions_url("https://gateway.example/v1/")
        == "https://gateway.example/v1/chat/completions"
    )


def test_chat_completions_url_adds_v1_to_origin() -> None:
    assert (
        chat_completions_url("https://gateway.example")
        == "https://gateway.example/v1/chat/completions"
    )


def test_2xx_integer_prompt_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "url": str(request.url),
                "auth": request.headers.get("Authorization"),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "model": "demo-model",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "length"}],
                "usage": {
                    "prompt_tokens": 17,
                    "completion_tokens": 1,
                    "prompt_tokens_details": {"cached_tokens": 5},
                },
            },
        )

    client, recorder = _make_client(tmp_path, monkeypatch, handler)
    record = client.complete(
        [{"role": "user", "content": "The quick brown fox.\n"}],
        kind="family_base",
    )
    assert record.status_code == 200
    assert record.error is None
    assert record.prompt_tokens == 17
    assert record.completion_tokens == 1
    assert record.content == "ok"
    assert record.usage is not None
    assert record.usage["prompt_tokens"] == 17
    assert record.usage["cached_tokens"] == 5
    assert record.metrics is not None
    assert record.metrics["billed_prompt_tokens"] == 12
    assert record.metrics["input_chars"] == len("The quick brown fox.\n")
    assert record.metrics["output_chars"] == 2
    assert record.metrics["rate_basis"] == "e2e_wall_clock"
    assert seen[0]["url"] == "https://gateway.example/v1/chat/completions"
    assert seen[0]["auth"] == f"Bearer {SECRET}"
    assert seen[0]["body"]["stream"] is False
    assert "max_tokens" not in seen[0]["body"]
    assert seen[0]["body"]["temperature"] == 0.0
    dumped = recorder.path.read_text(encoding="utf-8")
    assert SECRET not in dumped
    assert "Authorization" not in dumped
    assert "api_key" not in dumped


def test_2xx_missing_usage_prompt_tokens_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hi"}}]},
        )

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    record = client.complete([{"role": "user", "content": "x"}])
    assert record.status_code == 200
    assert record.prompt_tokens is None
    assert record.completion_tokens is None
    assert record.error is None


def test_2xx_non_integer_prompt_tokens_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"usage": {"prompt_tokens": "12", "completion_tokens": 1.5}},
        )

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    record = client.complete([{"role": "user", "content": "x"}])
    assert record.prompt_tokens is None
    assert record.completion_tokens is None


def test_500_retries_then_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1},
            },
        )

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    record = client.complete([{"role": "user", "content": "x"}])
    assert calls["n"] == 3
    assert record.status_code == 200
    assert record.prompt_tokens == 4
    assert record.error is None


def test_500_exhausted_returns_error_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": "still down"})

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    record = client.complete([{"role": "user", "content": "x"}])
    assert calls["n"] == 3
    assert record.status_code == 500
    assert record.prompt_tokens is None
    assert record.error is not None
    assert "500" in record.error


def test_401_no_retry_and_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "unauthorized"}})

    client, recorder = _make_client(tmp_path, monkeypatch, handler)
    record = client.complete([{"role": "user", "content": "x"}])
    assert calls["n"] == 1
    assert record.status_code == 401
    assert record.prompt_tokens is None
    assert record.error is not None
    dumped = recorder.path.read_text(encoding="utf-8")
    assert SECRET not in dumped


def test_max_tokens_none_omitted_from_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"usage": {"prompt_tokens": 3, "completion_tokens": 0}},
        )

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    client.complete([{"role": "user", "content": "x"}], max_tokens=None)
    assert "max_tokens" not in bodies[0]
    assert bodies[0]["stream"] is False


def test_connect_error_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"usage": {"prompt_tokens": 2}})

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    record = client.complete([{"role": "user", "content": "x"}])
    assert calls["n"] == 2
    assert record.prompt_tokens == 2


def test_recorder_file_never_contains_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == f"Bearer {SECRET}"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1},
            },
        )

    client, recorder = _make_client(tmp_path, monkeypatch, handler)
    client.complete([{"role": "user", "content": "hello"}])
    text = recorder.path.read_text(encoding="utf-8")
    assert SECRET not in text
    assert "Bearer" not in text
    row = json.loads(text)
    assert "api_key" not in row
    assert "Authorization" not in row
    assert "Authorization" not in row["request"]
    assert row["endpoint"] == "https://gateway.example/v1"


def test_stream_empty_sse_sets_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content="data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    rec = client.complete([{"role": "user", "content": "hi"}], stream=True)
    assert rec.status_code == 200
    assert rec.error == "stream: 无 SSE 事件"
    assert rec.content in (None, "")


def test_stream_error_event_sets_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        sse = 'data: {"type":"error","error":{"type":"overloaded_error","message":"busy"}}\n\n'
        return httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})

    client, _ = _make_client(tmp_path, monkeypatch, handler)
    rec = client.complete([{"role": "user", "content": "hi"}], stream=True)
    assert rec.error == "stream: busy"
