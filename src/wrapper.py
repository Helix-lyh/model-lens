"""网关聊天模板开销（wrapper 常数）。

对同一段 user text：API 报的 prompt_tokens 减去本地词表 encode 长度。
跨几段不同长度的 text，若某词表算出的差几乎不变（允许差 1），记 constant；
否则 drifted。缺整数 usage 或 HTTP 非 2xx 的条丢掉。有效条不到 2 条则整场 untrusted。

这一层只报壳子开销，不进家族结论，也不合成总分。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median_low
from typing import Literal

from src.types import Completer, CompletionRecord, Vocab
from src.usage import http_ok, record_prompt_tokens

WrapperStatus = Literal["constant", "drifted", "untrusted"]

DEFAULT_WRAPPER_TEXTS = (
    "hi",
    "hello",
    "Say OK.",
    "Please answer with a single word: yes or no, thanks.",
)

_MIN_VALID = 2
_CONSTANT_SPREAD = 1


@dataclass
class WrapperSample:
    text: str
    prompt_tokens: int | None
    dropped: bool
    drop_reason: str | None
    local_n: dict[str, int] = field(default_factory=dict)
    wrapper: dict[str, int | None] = field(default_factory=dict)


@dataclass
class WrapperCandidate:
    catalog_id: str
    wrappers: list[int]
    value: int | None
    spread: int | None
    status: WrapperStatus


@dataclass
class WrapperResult:
    status: WrapperStatus
    catalog_id: str | None
    value: int | None
    spread: int | None
    samples: list[WrapperSample] = field(default_factory=list)
    candidates: list[WrapperCandidate] = field(default_factory=list)
    untrusted_reason: str | None = None


def run_wrapper(
    client: Completer,
    catalog: dict[str, Vocab],
    texts: list[str] | None = None,
) -> WrapperResult:
    """对若干段 text 各打一次非流式请求，按词表算 wrapper 是否恒定。"""
    used = list(texts) if texts is not None else list(DEFAULT_WRAPPER_TEXTS)
    samples = [_measure(client, catalog, text) for text in used]
    candidates = [_score(kid, samples) for kid in catalog]
    return _decide(samples, candidates)


def format_wrapper_line(result: WrapperResult) -> str:
    """CLI 一行。例：wrapper=constant glm5 +36 spread=0"""
    if result.status == "untrusted":
        return "wrapper=untrusted"
    if result.status == "constant":
        signed = f"{result.value:+d}" if result.value is not None else "?"
        if result.catalog_id:
            return f"wrapper=constant {result.catalog_id} {signed} spread={result.spread}"
        return f"wrapper=constant {signed} spread={result.spread}"
    if result.catalog_id is None:
        return "wrapper=drifted"
    return f"wrapper=drifted {result.catalog_id} spread={result.spread}"


def _measure(client: Completer, catalog: dict[str, Vocab], text: str) -> WrapperSample:
    rec = client.complete(
        messages=[{"role": "user", "content": text}],
        temperature=0,
        max_tokens=None,
        extra=None,
        kind="wrapper",
        stream=False,
    )
    local_n = {kid: vocab.encode_len(text) for kid, vocab in catalog.items()}
    if not http_ok(rec):
        return WrapperSample(
            text=text,
            prompt_tokens=record_prompt_tokens(rec),
            dropped=True,
            drop_reason="http_non_2xx",
            local_n=local_n,
            wrapper={kid: None for kid in catalog},
        )
    prompt = record_prompt_tokens(rec)
    if prompt is None:
        return WrapperSample(
            text=text,
            prompt_tokens=None,
            dropped=True,
            drop_reason="missing_prompt_tokens",
            local_n=local_n,
            wrapper={kid: None for kid in catalog},
        )
    return WrapperSample(
        text=text,
        prompt_tokens=prompt,
        dropped=False,
        drop_reason=None,
        local_n=local_n,
        wrapper={kid: prompt - n for kid, n in local_n.items()},
    )


def _score(catalog_id: str, samples: list[WrapperSample]) -> WrapperCandidate:
    wrappers = [s.wrapper[catalog_id] for s in samples if not s.dropped]
    values = [w for w in wrappers if w is not None]
    if len(values) < _MIN_VALID:
        return WrapperCandidate(
            catalog_id=catalog_id,
            wrappers=values,
            value=None,
            spread=None,
            status="untrusted",
        )
    spread = max(values) - min(values)
    return WrapperCandidate(
        catalog_id=catalog_id,
        wrappers=values,
        value=_typical(values),
        spread=spread,
        status="constant" if spread <= _CONSTANT_SPREAD else "drifted",
    )


def _decide(samples: list[WrapperSample], candidates: list[WrapperCandidate]) -> WrapperResult:
    if not candidates:
        return WrapperResult(
            status="untrusted",
            catalog_id=None,
            value=None,
            spread=None,
            samples=samples,
            candidates=candidates,
            untrusted_reason="empty_catalog",
        )
    if all(c.status == "untrusted" for c in candidates):
        return WrapperResult(
            status="untrusted",
            catalog_id=None,
            value=None,
            spread=None,
            samples=samples,
            candidates=candidates,
            untrusted_reason="too_few_valid_samples",
        )

    constants = [c for c in candidates if c.status == "constant"]
    if constants:
        min_spread = min(c.spread if c.spread is not None else 0 for c in constants)
        tied = [c for c in constants if c.spread == min_spread]
        values = {c.value for c in tied}
        if len(tied) > 1:
            if len(values) > 1:
                # 多家尺子都恒定但开销不同，不猜是哪家
                return WrapperResult(
                    status="drifted",
                    catalog_id=None,
                    value=None,
                    spread=min_spread,
                    samples=samples,
                    candidates=candidates,
                )
            # 多家尺子量出同一常数：壳开销确实恒定，但不猜是哪家尺子
            winner = tied[0]
            return WrapperResult(
                status="constant",
                catalog_id=None,
                value=winner.value,
                spread=winner.spread,
                samples=samples,
                candidates=candidates,
            )
        winner = tied[0]
        return WrapperResult(
            status="constant",
            catalog_id=winner.catalog_id,
            value=winner.value,
            spread=winner.spread,
            samples=samples,
            candidates=candidates,
        )

    drifted = [c for c in candidates if c.status == "drifted"]
    winner = min(drifted, key=lambda c: (c.spread if c.spread is not None else 10**9, c.catalog_id))
    return WrapperResult(
        status="drifted",
        catalog_id=winner.catalog_id,
        value=winner.value,
        spread=winner.spread,
        samples=samples,
        candidates=candidates,
    )


def _typical(values: list[int]) -> int:
    """有唯一众数就用众数，并列则取偏低中位数。不稳定时也给中位数。"""
    counts = Counter(values)
    best = max(counts.values())
    modes = [v for v, n in counts.items() if n == best]
    if len(modes) == 1:
        return modes[0]
    return int(median_low(values))



