"""Module F：词表差分计分。公式与 fail-closed 见 docs/design.md §2.1–2.3。"""

from __future__ import annotations

from typing import Any

from src.types import (
    CompletionRecord,
    Confidence,
    FamilyResult,
    FamilyScore,
    Probe,
    ProbeDelta,
    Vocab,
)

BASE = "The quick brown fox.\n"

_MIN_VALID_PROBES = 8
_MIN_EXACT_HITS = 6
_L1_TIE_MARGIN = 3
_HIGH_HITS = 8
_HIGH_HIT_GAP = 3
_DELTA_SLACK = 500


def run_family(
    client: Any,
    catalog: dict[str, Vocab],
    base: str,
    probes: list[Probe],
    *,
    claimed_model: str | None = None,
) -> FamilyResult:
    """对 BASE 与每条 BASE+x 做非流式差分，按 L1 / exact_hits 选家族。

    claimed_model 不参与计分。协议探测不在此调用。
    """
    del claimed_model

    base_rec = _complete(client, base, kind="family_base")
    if not _http_ok(base_rec):
        return _untrusted("base_http_error", probes=[], n_probes=0)
    if not _int_tokens(base_rec.prompt_tokens):
        return _untrusted("base_missing_prompt_tokens", probes=[], n_probes=0)

    prompt_tokens_base: int = base_rec.prompt_tokens  # type: ignore[assignment]

    deltas: list[ProbeDelta] = []
    for probe in probes:
        deltas.append(
            _measure_probe(
                client,
                catalog=catalog,
                base=base,
                probe=probe,
                prompt_tokens_base=prompt_tokens_base,
            )
        )

    kept = [d for d in deltas if not d.dropped]
    n_used = len(kept)
    if n_used < _MIN_VALID_PROBES:
        scores = _score_candidates(catalog, kept) if kept else []
        return _untrusted(
            "too_few_valid_probes",
            probes=deltas,
            n_probes=n_used,
            scores=scores,
        )

    scores = _score_candidates(catalog, kept)
    if not scores:
        return _untrusted(
            "empty_catalog",
            probes=deltas,
            n_probes=n_used,
            scores=[],
        )

    best = scores[0]
    second = scores[1] if len(scores) >= 2 else None

    if _ambiguous(best, second, n_used):
        return _result(
            status="ambiguous",
            family="ambiguous",
            confidence=None,
            best=best,
            second=second,
            n_probes=n_used,
            scores=scores,
            probes=deltas,
        )

    return _result(
        status="ok",
        family=best.catalog_id,
        confidence=_confidence(best, second),
        best=best,
        second=second,
        n_probes=n_used,
        scores=scores,
        probes=deltas,
    )


def format_family_line(result: FamilyResult) -> str:
    """CLI 一行：family=glm5 hits=10/14 l1=2 runner_up=qwen2_5 hits=6/14 l1=11 confidence=high"""
    if result.status == "token_untrusted":
        return "family=token_untrusted"
    parts = [f"family={result.family}"]
    if result.n_probes:
        parts.append(f"hits={result.hits}/{result.n_probes}")
    if result.l1 is not None:
        parts.append(f"l1={result.l1}")
    if result.runner_up is not None:
        parts.append(f"runner_up={result.runner_up}")
        if result.runner_up_hits is not None:
            parts.append(f"hits={result.runner_up_hits}/{result.n_probes}")
        if result.runner_up_l1 is not None:
            parts.append(f"l1={result.runner_up_l1}")
    if result.status == "ok" and result.confidence:
        parts.append(f"confidence={result.confidence}")
    return " ".join(parts)


def run_protocol_probes(client: Any, *, enabled: bool = False) -> list[CompletionRecord]:
    """预留。不进入家族结论；默认不启用，run_family 不调用。"""
    del client
    if not enabled:
        return []
    return []


def _complete(client: Any, text: str, *, kind: str) -> CompletionRecord:
    try:
        return client.complete(
            messages=[{"role": "user", "content": text}],
            temperature=0,
            max_tokens=None,
            kind=kind,
            stream=False,
        )
    except Exception as exc:  # noqa: BLE001 — 成对失败记缺测，不中断整场
        return CompletionRecord(
            kind=kind,
            endpoint="",
            model="",
            request={"messages": [{"role": "user", "content": text}]},
            status_code=None,
            latency_ms=0,
            prompt_tokens=None,
            completion_tokens=None,
            content=None,
            error=str(exc),
        )


def _measure_probe(
    client: Any,
    *,
    catalog: dict[str, Vocab],
    base: str,
    probe: Probe,
    prompt_tokens_base: int,
) -> ProbeDelta:
    n_hat = _n_hats(catalog, base, probe)
    text = base + probe.text
    rec = _complete(client, text, kind=f"family_probe:{probe.id}")

    if not _http_ok(rec):
        return _dropped(
            probe,
            prompt_tokens_base=prompt_tokens_base,
            prompt_tokens_probe=rec.prompt_tokens if _int_tokens(rec.prompt_tokens) else None,
            n_hat=n_hat,
            reason="http_non_2xx",
        )
    if not _int_tokens(rec.prompt_tokens):
        return _dropped(
            probe,
            prompt_tokens_base=prompt_tokens_base,
            prompt_tokens_probe=None,
            n_hat=n_hat,
            reason="missing_prompt_tokens",
        )

    prompt_tokens_probe: int = rec.prompt_tokens  # type: ignore[assignment]
    delta_api = prompt_tokens_probe - prompt_tokens_base
    if delta_api < 1 or delta_api > len(probe.text) + _DELTA_SLACK:
        return _dropped(
            probe,
            prompt_tokens_base=prompt_tokens_base,
            prompt_tokens_probe=prompt_tokens_probe,
            n_hat=n_hat,
            reason="delta_out_of_range",
            delta_api=delta_api,
        )

    return ProbeDelta(
        probe_id=probe.id,
        text=probe.text,
        escaped=probe.escaped,
        prompt_tokens_base=prompt_tokens_base,
        prompt_tokens_probe=prompt_tokens_probe,
        delta_api=delta_api,
        dropped=False,
        drop_reason=None,
        n_hat=n_hat,
    )


def _n_hats(catalog: dict[str, Vocab], base: str, probe: Probe) -> dict[str, int]:
    return {
        kid: vocab.n_hat(base, probe.text, escaped=probe.escaped)
        for kid, vocab in catalog.items()
    }


def _score_candidates(
    catalog: dict[str, Vocab],
    kept: list[ProbeDelta],
) -> list[FamilyScore]:
    scores: list[FamilyScore] = []
    for kid in catalog:
        exact_hits = 0
        l1 = 0
        for pd in kept:
            nh = pd.n_hat[kid]
            delta = pd.delta_api
            if delta is None:
                continue
            if delta == nh:
                exact_hits += 1
            l1 += abs(delta - nh)
        scores.append(
            FamilyScore(
                catalog_id=kid,
                exact_hits=exact_hits,
                l1=l1,
                n_used=len(kept),
            )
        )
    scores.sort(key=lambda s: (s.l1, -s.exact_hits))
    return scores


def _ambiguous(best: FamilyScore, second: FamilyScore | None, n_used: int) -> bool:
    if second is not None and (second.l1 - best.l1) < _L1_TIE_MARGIN:
        return True
    if best.l1 >= 2 * n_used:
        return True
    if best.exact_hits < _MIN_EXACT_HITS:
        return True
    return False


def _confidence(best: FamilyScore, second: FamilyScore | None) -> Confidence:
    if second is None:
        return "high" if best.exact_hits >= _HIGH_HITS else "medium"
    hits_gap = best.exact_hits - second.exact_hits
    if best.exact_hits >= _HIGH_HITS and hits_gap >= _HIGH_HIT_GAP:
        return "high"
    if best.exact_hits > second.exact_hits:
        return "medium"
    return "low"


def _http_ok(rec: CompletionRecord) -> bool:
    sc = rec.status_code
    return sc is not None and 200 <= sc < 300


def _int_tokens(value: int | None) -> bool:
    return type(value) is int


def _dropped(
    probe: Probe,
    *,
    prompt_tokens_base: int | None,
    prompt_tokens_probe: int | None,
    n_hat: dict[str, int],
    reason: str,
    delta_api: int | None = None,
) -> ProbeDelta:
    return ProbeDelta(
        probe_id=probe.id,
        text=probe.text,
        escaped=probe.escaped,
        prompt_tokens_base=prompt_tokens_base,
        prompt_tokens_probe=prompt_tokens_probe,
        delta_api=delta_api,
        dropped=True,
        drop_reason=reason,
        n_hat=n_hat,
    )


def _untrusted(
    reason: str,
    *,
    probes: list[ProbeDelta],
    n_probes: int,
    scores: list[FamilyScore] | None = None,
) -> FamilyResult:
    return FamilyResult(
        status="token_untrusted",
        family="token_untrusted",
        confidence=None,
        hits=0,
        n_probes=n_probes,
        l1=None,
        runner_up=None,
        runner_up_hits=None,
        runner_up_l1=None,
        scores=scores or [],
        probes=probes,
        untrusted_reason=reason,
    )


def _result(
    *,
    status: str,
    family: str,
    confidence: Confidence | None,
    best: FamilyScore,
    second: FamilyScore | None,
    n_probes: int,
    scores: list[FamilyScore],
    probes: list[ProbeDelta],
) -> FamilyResult:
    return FamilyResult(
        status=status,  # type: ignore[arg-type]
        family=family,
        confidence=confidence,
        hits=best.exact_hits,
        n_probes=n_probes,
        l1=best.l1,
        runner_up=second.catalog_id if second is not None else None,
        runner_up_hits=second.exact_hits if second is not None else None,
        runner_up_l1=second.l1 if second is not None else None,
        scores=scores,
        probes=probes,
        untrusted_reason=None,
    )
