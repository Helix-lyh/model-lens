"""归一各家 usage，并派生缓存效率 / 消耗 / 端到端速率。

速率默认按整段墙钟算（含排队+预填），不是流式 decode TPS。
禁止用本地词表估算 prompt_tokens。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

def int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


@dataclass
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass
class RequestMetrics:
    input_chars: int = 0
    output_chars: int = 0
    cache_hit_ratio: float | None = None
    billed_prompt_tokens: int | None = None
    e2e_output_tps: float | None = None
    e2e_total_tps: float | None = None
    ttft_ms: int | None = None
    decode_tps: float | None = None
    rate_basis: str = "e2e_wall_clock"


def nested_int(obj: object, *keys: str) -> int | None:
    cur: object = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return int_or_none(cur)


def extract_token_usage(data: object) -> TokenUsage:
    """从原始 JSON 抽 usage。缺字段保持 None，不估算。"""
    if not isinstance(data, dict):
        return TokenUsage()
    if isinstance(data.get("usageMetadata"), dict):
        return _from_google(data["usageMetadata"])
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return TokenUsage()
    return _from_usage_object(usage)


def _from_usage_object(usage: dict[str, Any]) -> TokenUsage:
    prompt = int_or_none(usage.get("prompt_tokens"))
    if prompt is None:
        prompt = int_or_none(usage.get("input_tokens"))
    if prompt is None:
        prompt = int_or_none(usage.get("inputTokens"))
    completion = int_or_none(usage.get("completion_tokens"))
    if completion is None:
        completion = int_or_none(usage.get("output_tokens"))
    if completion is None:
        completion = int_or_none(usage.get("outputTokens"))
    total = int_or_none(usage.get("total_tokens"))
    if total is None:
        total = int_or_none(usage.get("totalTokens"))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion

    cached = int_or_none(usage.get("cached_tokens"))
    if cached is None:
        cached = int_or_none(usage.get("cache_read_input_tokens"))
    if cached is None:
        cached = int_or_none(usage.get("prompt_cache_hit_tokens"))
    if cached is None:
        cached = int_or_none(usage.get("cacheReadInputTokens"))
    if cached is None:
        cached = nested_int(usage, "prompt_tokens_details", "cached_tokens")
    if cached is None:
        cached = nested_int(usage, "input_tokens_details", "cached_tokens")

    cache_write = int_or_none(usage.get("cache_creation_input_tokens"))
    if cache_write is None:
        cache_write = int_or_none(usage.get("cacheWriteInputTokens"))
    if cache_write is None:
        created = usage.get("cache_creation")
        if isinstance(created, dict):
            parts = [
                int_or_none(created.get("ephemeral_5m_input_tokens")),
                int_or_none(created.get("ephemeral_1h_input_tokens")),
            ]
            known = [p for p in parts if p is not None]
            cache_write = sum(known) if known else None

    reasoning = nested_int(usage, "completion_tokens_details", "reasoning_tokens")
    if reasoning is None:
        reasoning = nested_int(usage, "output_tokens_details", "reasoning_tokens")
    if reasoning is None:
        reasoning = int_or_none(usage.get("reasoning_tokens"))

    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        cached_tokens=cached,
        cache_write_tokens=cache_write,
        reasoning_tokens=reasoning,
    )


def _from_google(meta: dict[str, Any]) -> TokenUsage:
    prompt = int_or_none(meta.get("promptTokenCount"))
    completion = int_or_none(meta.get("candidatesTokenCount"))
    total = int_or_none(meta.get("totalTokenCount"))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        cached_tokens=int_or_none(meta.get("cachedContentTokenCount")),
        reasoning_tokens=int_or_none(meta.get("thoughtsTokenCount")),
    )


def count_text_chars(value: object) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(count_text_chars(item) for item in value)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return len(value["text"])
        if isinstance(value.get("content"), (str, list, dict)):
            return count_text_chars(value["content"])
        if isinstance(value.get("parts"), list):
            return count_text_chars(value["parts"])
        return 0
    return 0


def count_request_chars(request: dict[str, Any] | None) -> int:
    if not request:
        return 0
    if "messages" in request:
        return count_text_chars(request.get("messages"))
    if "input" in request:
        return count_text_chars(request.get("input"))
    if "contents" in request:
        return count_text_chars(request.get("contents"))
    return 0


def derive_metrics(
    usage: TokenUsage,
    *,
    latency_ms: int,
    input_chars: int,
    output_chars: int,
    ttft_ms: int | None = None,
) -> RequestMetrics:
    cache_hit_ratio = None
    if usage.prompt_tokens and usage.prompt_tokens > 0 and usage.cached_tokens is not None:
        cache_hit_ratio = round(usage.cached_tokens / usage.prompt_tokens, 6)

    billed = None
    if usage.prompt_tokens is not None and usage.cached_tokens is not None:
        billed = max(0, usage.prompt_tokens - usage.cached_tokens)

    e2e_output = _tps(usage.completion_tokens, latency_ms)
    e2e_total = _tps(usage.total_tokens, latency_ms)
    decode = None
    rate_basis = "e2e_wall_clock"
    if (
        ttft_ms is not None
        and usage.completion_tokens
        and latency_ms > ttft_ms
        and usage.completion_tokens > 0
    ):
        decode = _tps(usage.completion_tokens, latency_ms - ttft_ms)
        rate_basis = "ttft_to_end"

    return RequestMetrics(
        input_chars=input_chars,
        output_chars=output_chars,
        cache_hit_ratio=cache_hit_ratio,
        billed_prompt_tokens=billed,
        e2e_output_tps=e2e_output,
        e2e_total_tps=e2e_total,
        ttft_ms=ttft_ms,
        decode_tps=decode,
        rate_basis=rate_basis,
    )


def _tps(tokens: int | None, duration_ms: int) -> float | None:
    if not tokens or duration_ms <= 0:
        return None
    return round(tokens / (duration_ms / 1000.0), 4)


def summarize_jsonl(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return None
    return summarize_records(rows)


def summarize_records(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    ok = [r for r in rows if isinstance(r.get("status_code"), int) and 200 <= r["status_code"] < 300]
    prompts = _ints(ok, "prompt_tokens")
    completions = _ints(ok, "completion_tokens")
    cached = _nested_ints(ok, "usage", "cached_tokens")
    billed = _nested_ints(ok, "metrics", "billed_prompt_tokens")
    latencies = [r["latency_ms"] for r in ok if isinstance(r.get("latency_ms"), int)]
    out_tps = _nested_floats(ok, "metrics", "e2e_output_tps")
    decode_tps = _nested_floats(ok, "metrics", "decode_tps")
    ttfts = _nested_ints(ok, "metrics", "ttft_ms")
    in_chars = _nested_ints(ok, "metrics", "input_chars")
    out_chars = _nested_ints(ok, "metrics", "output_chars")
    hit_ratios = _nested_floats(ok, "metrics", "cache_hit_ratio")
    streamed = any(
        isinstance(r.get("metrics"), dict) and r["metrics"].get("ttft_ms") is not None for r in ok
    )

    return {
        "requests": n,
        "ok": len(ok),
        "prompt_tokens": _sum_max(prompts),
        "completion_tokens": _sum_max(completions),
        "cached_tokens": _sum_max(cached),
        "billed_prompt_tokens": _sum_max(billed),
        "input_chars": _sum_max(in_chars),
        "output_chars": _sum_max(out_chars),
        "latency_ms": _avg_max(latencies),
        "e2e_output_tps": _avg_max(out_tps, ndigits=4),
        "ttft_ms": _avg_max(ttfts),
        "decode_tps": _avg_max(decode_tps, ndigits=4),
        "cache_hit_ratio": round(sum(hit_ratios) / len(hit_ratios), 6) if hit_ratios else None,
        "rate_basis": "ttft_to_end" if decode_tps else "e2e_wall_clock",
        "note": (
            "decode_tps = (完成−TTFT) 墙钟；中转 streaming 的 usage 常不可信。"
            if streamed
            else "e2e_output_tps 含排队与预填；家族探针输出很短时速率没有参考价值"
        ),
    }


def usage_asdict(usage: TokenUsage) -> dict[str, Any]:
    return asdict(usage)


def metrics_asdict(metrics: RequestMetrics) -> dict[str, Any]:
    return asdict(metrics)


def _ints(rows: list[dict[str, Any]], key: str) -> list[int]:
    out: list[int] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            out.append(value)
    return out


def _nested_ints(rows: list[dict[str, Any]], *keys: str) -> list[int]:
    out: list[int] = []
    for row in rows:
        value: object = row
        for key in keys:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            out.append(value)
    return out


def _nested_floats(rows: list[dict[str, Any]], *keys: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        value: object = row
        for key in keys:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append(float(value))
    return out


def _sum_max(values: list[int]) -> dict[str, int] | None:
    if not values:
        return None
    return {"sum": sum(values), "max": max(values)}


def _avg_max(values: list[int] | list[float], *, ndigits: int = 1) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "avg": round(sum(values) / len(values), ndigits),
        "max": round(max(values), ndigits),
    }
