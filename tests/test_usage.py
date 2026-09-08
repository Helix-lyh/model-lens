from __future__ import annotations

from src.types import CompletionRecord
from src.usage import (
    TokenUsage,
    count_request_chars,
    derive_metrics,
    extract_token_usage,
    http_ok,
    summarize_records,
)


def _rec(*, status_code: int | None = 200, error: str | None = None) -> CompletionRecord:
    return CompletionRecord(
        kind="t",
        endpoint="https://example.test/v1",
        model="demo",
        request={},
        status_code=status_code,
        latency_ms=1,
        prompt_tokens=1,
        completion_tokens=0,
        content="x",
        error=error,
    )


def test_http_ok_rejects_error_on_2xx() -> None:
    assert http_ok(_rec(status_code=200, error=None)) is True
    assert http_ok(_rec(status_code=200, error="stream: 无 SSE 事件")) is False
    assert http_ok(_rec(status_code=500, error=None)) is False


def test_openai_cached_and_reasoning() -> None:
    usage = extract_token_usage(
        {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 80},
                "completion_tokens_details": {"reasoning_tokens": 5},
            }
        }
    )
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 20
    assert usage.cached_tokens == 80
    assert usage.reasoning_tokens == 5
    metrics = derive_metrics(usage, latency_ms=2000, input_chars=40, output_chars=10)
    assert metrics.cache_hit_ratio == 0.8
    assert metrics.billed_prompt_tokens == 20
    assert metrics.e2e_output_tps == 10.0
    assert metrics.rate_basis == "e2e_wall_clock"


def test_anthropic_cache_read_write() -> None:
    usage = extract_token_usage(
        {
            "usage": {
                "input_tokens": 50,
                "output_tokens": 8,
                "cache_read_input_tokens": 40,
                "cache_creation_input_tokens": 10,
            }
        }
    )
    assert usage.prompt_tokens == 50
    assert usage.cached_tokens == 40
    assert usage.cache_write_tokens == 10


def test_deepseek_prompt_cache_hit() -> None:
    usage = extract_token_usage(
        {"usage": {"prompt_tokens": 30, "completion_tokens": 3, "prompt_cache_hit_tokens": 12}}
    )
    assert usage.cached_tokens == 12


def test_google_usage_metadata() -> None:
    usage = extract_token_usage(
        {
            "usageMetadata": {
                "promptTokenCount": 9,
                "candidatesTokenCount": 2,
                "totalTokenCount": 11,
                "cachedContentTokenCount": 4,
                "thoughtsTokenCount": 1,
            }
        }
    )
    assert usage.prompt_tokens == 9
    assert usage.cached_tokens == 4
    assert usage.reasoning_tokens == 1


def test_bedrock_camel_case_usage() -> None:
    usage = extract_token_usage(
        {
            "usage": {
                "inputTokens": 18,
                "outputTokens": 2,
                "totalTokens": 20,
                "cacheReadInputTokens": 6,
                "cacheWriteInputTokens": 3,
            }
        }
    )
    assert usage.prompt_tokens == 18
    assert usage.completion_tokens == 2
    assert usage.total_tokens == 20
    assert usage.cached_tokens == 6
    assert usage.cache_write_tokens == 3


def test_missing_usage_stays_none() -> None:
    usage = extract_token_usage({"choices": []})
    assert usage.prompt_tokens is None
    assert usage.cached_tokens is None


def test_non_integer_usage_stays_none() -> None:
    usage = extract_token_usage(
        {"usage": {"prompt_tokens": "12", "completion_tokens": True, "input_tokens": 7.5}}
    )
    assert usage.prompt_tokens is None
    assert usage.completion_tokens is None


def test_anthropic_ephemeral_cache_write_sum() -> None:
    usage = extract_token_usage(
        {
            "usage": {
                "input_tokens": 10,
                "output_tokens": 1,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 3,
                    "ephemeral_1h_input_tokens": 4,
                },
            }
        }
    )
    assert usage.cache_write_tokens == 7


def test_count_request_chars() -> None:
    assert count_request_chars({"messages": [{"role": "user", "content": "abcd"}]}) == 4


def test_decode_tps_when_ttft_present() -> None:
    metrics = derive_metrics(
        TokenUsage(completion_tokens=10, total_tokens=10),
        latency_ms=1500,
        input_chars=1,
        output_chars=10,
        ttft_ms=500,
    )
    assert metrics.decode_tps == 10.0
    assert metrics.rate_basis == "ttft_to_end"


def test_summarize_records() -> None:
    summary = summarize_records(
        [
            {
                "status_code": 200,
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "latency_ms": 1000,
                "usage": {"cached_tokens": 40},
                "metrics": {
                    "billed_prompt_tokens": 60,
                    "e2e_output_tps": 10.0,
                    "ttft_ms": 200,
                    "decode_tps": 12.5,
                    "input_chars": 20,
                    "output_chars": 5,
                    "cache_hit_ratio": 0.4,
                },
            },
            {"status_code": 500, "prompt_tokens": None},
        ]
    )
    assert summary["requests"] == 2
    assert summary["ok"] == 1
    assert summary["prompt_tokens"] == {"sum": 100, "max": 100}
    assert summary["cache_hit_ratio"] == 0.4
    assert summary["ttft_ms"] == {"avg": 200.0, "max": 200.0}
    assert summary["decode_tps"] == {"avg": 12.5, "max": 12.5}
    assert summary["rate_basis"] == "ttft_to_end"
