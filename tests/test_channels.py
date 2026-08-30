from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.channels.presets import infer_channel_from_url
from src.channels.resolve import resolve_channel
from src.client import ChatClient, JsonlRecorder
from src.types import Endpoint


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: Endpoint,
    handler,
) -> ChatClient:
    monkeypatch.setenv(endpoint.api_key_env, "sk-secret-channel")
    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=60.0)
    return ChatClient(
        endpoint,
        JsonlRecorder(tmp_path / "requests.jsonl"),
        http_client=http,
    )


def test_infer_official_hosts() -> None:
    assert infer_channel_from_url("https://open.bigmodel.cn/api/paas/v4") == "zhipu"
    assert infer_channel_from_url("https://api.anthropic.com") == "anthropic"
    assert infer_channel_from_url("https://generativelanguage.googleapis.com") == "google"
    assert infer_channel_from_url("https://dashscope.aliyuncs.com/compatible-mode/v1") == "dashscope"
    assert infer_channel_from_url("https://unknown.example/v1") is None


def test_zhipu_preset_uses_v4_not_v1() -> None:
    resolved = resolve_channel(
        Endpoint(base_url="", api_key_env="ZHIPU_API_KEY", model="glm-4.5-flash", channel="zhipu")
    )
    assert resolved.api == "openai-completions"
    assert resolved.base_url.endswith("/api/paas/v4")
    assert resolved.from_preset is True


def test_unknown_channel_errors() -> None:
    with pytest.raises(ValueError, match="未知 channel"):
        resolve_channel(
            Endpoint(
                base_url="https://x.example/v1",
                api_key_env="K",
                model="m",
                channel="not-a-vendor",
            )
        )


def test_anthropic_request_and_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json={
                "id": "msg-1",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 21, "output_tokens": 1},
            },
        )

    ep = Endpoint(
        base_url="",
        api_key_env="ANTHROPIC_API_KEY",
        model="claude-sonnet-4-5",
        channel="anthropic",
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}])
    assert rec.prompt_tokens == 21
    assert rec.completion_tokens == 1
    assert rec.usage is not None
    assert rec.usage["prompt_tokens"] == 21
    assert rec.api == "anthropic-messages"
    assert rec.channel == "anthropic"
    assert seen[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert seen[0]["headers"]["x-api-key"] == "sk-secret-channel"
    assert seen[0]["headers"]["anthropic-version"]
    assert "Authorization" not in {k.title(): k for k in seen[0]["headers"]}
    assert seen[0]["body"]["max_tokens"] == 64000
    assert "stream" not in seen[0]["body"] or seen[0]["body"].get("stream") is False
    dumped = (tmp_path / "requests.jsonl").read_text(encoding="utf-8")
    assert "sk-secret-channel" not in dumped


def test_google_request_and_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "headers": dict(request.headers), "body": json.loads(request.content)})
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 1},
            },
        )

    ep = Endpoint(
        base_url="",
        api_key_env="GEMINI_API_KEY",
        model="gemini-2.5-flash",
        channel="google",
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}])
    assert rec.prompt_tokens == 9
    assert rec.api == "google-generative-ai"
    assert ":generateContent" in seen[0]["url"]
    assert "gemini-2.5-flash" in seen[0]["url"]
    assert seen[0]["headers"]["x-goog-api-key"] == "sk-secret-channel"
    assert "maxOutputTokens" not in seen[0]["body"]["generationConfig"]


def test_openai_responses_input_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "body": json.loads(request.content)})
        return httpx.Response(
            200,
            json={"usage": {"input_tokens": 13, "output_tokens": 1}, "output_text": "ok"},
        )

    ep = Endpoint(
        base_url="",
        api_key_env="OPENAI_API_KEY",
        model="gpt-4.1-mini",
        channel="openai-responses",
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}])
    assert rec.prompt_tokens == 13
    assert rec.api == "openai-responses"
    assert seen[0]["url"].endswith("/v1/responses")
    assert "max_output_tokens" not in seen[0]["body"]
    assert seen[0]["body"]["input"] == "hi"


def test_azure_deployments_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert request.headers.get("api-key") == "sk-secret-channel"
        return httpx.Response(200, json={"usage": {"prompt_tokens": 4, "completion_tokens": 1}})

    ep = Endpoint(
        base_url="https://demo.openai.azure.com",
        api_key_env="AZURE_OPENAI_API_KEY",
        model="my-gpt4o",
        channel="azure",
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}])
    assert rec.prompt_tokens == 4
    assert "deployments/my-gpt4o/chat/completions" in seen[0]
    assert "api-version=2024-10-21" in seen[0]


def test_deepseek_v4_sends_official_max_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"usage": {"prompt_tokens": 2, "completion_tokens": 1}})

    ep = Endpoint(
        base_url="",
        api_key_env="DEEPSEEK_API_KEY",
        model="deepseek-v4-flash",
        channel="deepseek",
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    client.complete([{"role": "user", "content": "hi"}])
    assert bodies[0]["max_tokens"] == 384000


def test_o_series_omits_max_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"usage": {"prompt_tokens": 2}})

    ep = Endpoint(
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model="o3-mini",
        channel="openai",
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    client.complete([{"role": "user", "content": "hi"}])
    assert "max_tokens" not in bodies[0]


def test_custom_api_plus_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 1}})

    ep = Endpoint(
        base_url="https://proxy.example",
        api_key_env="TARGET_KEY",
        model="claude-sonnet-4-5",
        api="anthropic-messages",
        compat={"auth": "x-api-key"},
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}])
    assert rec.prompt_tokens == 5
    assert seen[0] == "https://proxy.example/v1/messages"


def test_infer_cloud_hosts() -> None:
    assert infer_channel_from_url("https://bedrock-runtime.us-west-2.amazonaws.com") == "bedrock"
    assert infer_channel_from_url("https://us-central1-aiplatform.googleapis.com") == "vertex"


def test_bedrock_converse_request_and_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json={
                "output": {"message": {"content": [{"text": "ok"}]}},
                "usage": {
                    "inputTokens": 18,
                    "outputTokens": 2,
                    "totalTokens": 20,
                    "cacheReadInputTokens": 6,
                },
            },
        )

    ep = Endpoint(
        base_url="",
        api_key_env="AWS_BEARER_TOKEN_BEDROCK",
        model="anthropic.claude-sonnet-4-20250514-v1:0",
        channel="bedrock",
        compat={"region": "us-west-2"},
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}])
    assert rec.prompt_tokens == 18
    assert rec.completion_tokens == 2
    assert rec.usage is not None
    assert rec.usage["cached_tokens"] == 6
    assert rec.api == "bedrock-converse"
    assert rec.channel == "bedrock"
    assert "bedrock-runtime.us-west-2.amazonaws.com/model/" in seen[0]["url"]
    assert seen[0]["url"].endswith("/converse")
    assert "claude-sonnet-4" in seen[0]["url"]
    assert seen[0]["headers"]["authorization"] == "Bearer sk-secret-channel"
    assert "maxTokens" not in seen[0]["body"].get("inferenceConfig", {})
    assert seen[0]["body"]["messages"][0]["content"][0]["text"] == "hi"


def test_vertex_generate_content_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "headers": dict(request.headers)})
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 1},
            },
        )

    ep = Endpoint(
        base_url="",
        api_key_env="VERTEX_ACCESS_TOKEN",
        model="gemini-2.5-flash",
        channel="vertex",
        compat={"project": "demo-proj", "location": "europe-west1"},
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}])
    assert rec.prompt_tokens == 7
    assert rec.api == "google-vertex"
    assert rec.channel == "vertex"
    url = seen[0]["url"]
    assert "europe-west1-aiplatform.googleapis.com" in url
    assert "/projects/demo-proj/locations/europe-west1/" in url
    assert "models/gemini-2.5-flash:generateContent" in url
    assert seen[0]["headers"]["authorization"] == "Bearer sk-secret-channel"


def test_bedrock_stream_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/converse-stream" not in str(request.url)
        return httpx.Response(
            200,
            json={
                "output": {"message": {"content": [{"text": "ok"}]}},
                "usage": {"inputTokens": 3, "outputTokens": 1},
            },
        )

    ep = Endpoint(
        base_url="",
        api_key_env="AWS_BEARER_TOKEN_BEDROCK",
        model="amazon.titan-text-lite-v1",
        channel="bedrock",
    )
    client = _client(tmp_path, monkeypatch, ep, handler)
    rec = client.complete([{"role": "user", "content": "hi"}], stream=True)
    assert rec.prompt_tokens == 3
    assert rec.metrics is not None
    assert rec.metrics["stream_requested"] is True
    assert rec.metrics["stream_used"] is False
    assert rec.metrics.get("stream_note")
