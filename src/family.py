"""Module F：词表差分计分。公式与 fail-closed 见 docs/design.md §2.1–2.3。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.types import (
    DEFAULT_CONCURRENCY,
    Completer,
    CompletionRecord,
    Confidence,
    FamilyResult,
    FamilyScore,
    Probe,
    ProbeDelta,
    Vocab,
)
from src.usage import http_ok, int_or_none, record_prompt_tokens

_MIN_VALID_PROBES = 8
_MIN_EXACT_HITS = 6
_L1_TIE_MARGIN = 3
_HIGH_HITS = 8
_HIGH_HIT_GAP = 3
_DELTA_SLACK = 500


def run_family(
    client: Completer,
    catalog: dict[str, Vocab],
    base: str,
    probes: list[Probe],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> FamilyResult:
    """对 BASE 与每条 BASE+x 做非流式差分，按 L1 / exact_hits 选家族。

    声称型号不参与计分。协议探测不在此调用。
    """
    base_rec = _complete(client, base, kind="family_base")
    if not http_ok(base_rec):
        return _untrusted("base_http_error", probes=[], n_probes=0)
    prompt_tokens_base = record_prompt_tokens(base_rec)
    if prompt_tokens_base is None:
        return _untrusted("base_missing_prompt_tokens", probes=[], n_probes=0)
    cached_tokens_base = _record_cached_tokens(base_rec)
    if _cached_exceeds_prompt(prompt_tokens_base, cached_tokens_base):
        return _untrusted("base_cached_gt_prompt", probes=[], n_probes=0)

    deltas = _measure_probes(
        client,
        catalog=catalog,
        base=base,
        probes=probes,
        prompt_tokens_base=prompt_tokens_base,
        cached_tokens_base=cached_tokens_base,
        concurrency=concurrency,
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


def _complete(client: Completer, text: str, *, kind: str) -> CompletionRecord:
    return client.complete(
        messages=[{"role": "user", "content": text}],
        temperature=0,
        max_tokens=None,
        kind=kind,
        stream=False,
    )


def _measure_probes(
    client: Completer,
    *,
    catalog: dict[str, Vocab],
    base: str,
    probes: list[Probe],
    prompt_tokens_base: int,
    cached_tokens_base: int | None,
    concurrency: int,
) -> list[ProbeDelta]:
    workers = max(1, int(concurrency))

    def _one(probe: Probe) -> ProbeDelta:
        return _measure_probe(
            client,
            catalog=catalog,
            base=base,
            probe=probe,
            prompt_tokens_base=prompt_tokens_base,
            cached_tokens_base=cached_tokens_base,
        )

    if workers == 1 or len(probes) <= 1:
        return [_one(probe) for probe in probes]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, probes))


def _measure_probe(
    client: Completer,
    *,
    catalog: dict[str, Vocab],
    base: str,
    probe: Probe,
    prompt_tokens_base: int,
    cached_tokens_base: int | None,
) -> ProbeDelta:
    n_hat = _n_hats(catalog, base, probe)
    text = base + probe.text
    rec = _complete(client, text, kind=f"family_probe:{probe.id}")

    if not http_ok(rec):
        return _dropped(
            probe,
            prompt_tokens_base=prompt_tokens_base,
            prompt_tokens_probe=record_prompt_tokens(rec),
            n_hat=n_hat,
            reason="http_non_2xx",
        )
    prompt_tokens_probe = record_prompt_tokens(rec)
    if prompt_tokens_probe is None:
        return _dropped(
            probe,
            prompt_tokens_base=prompt_tokens_base,
            prompt_tokens_probe=None,
            n_hat=n_hat,
            reason="missing_prompt_tokens",
        )
    cached_tokens_probe = _record_cached_tokens(rec)
    if _cached_exceeds_prompt(prompt_tokens_probe, cached_tokens_probe):
        return _dropped(
            probe,
            prompt_tokens_base=prompt_tokens_base,
            prompt_tokens_probe=prompt_tokens_probe,
            n_hat=n_hat,
            reason="cached_gt_prompt",
        )
    if _cache_inconsistent(cached_tokens_base, cached_tokens_probe):
        return _dropped(
            probe,
            prompt_tokens_base=prompt_tokens_base,
            prompt_tokens_probe=prompt_tokens_probe,
            n_hat=n_hat,
            reason="cache_inconsistent",
        )

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


def _record_cached_tokens(rec: CompletionRecord) -> int | None:
    usage = rec.usage
    if not isinstance(usage, dict):
        return None
    return int_or_none(usage.get("cached_tokens"))


def _cached_exceeds_prompt(prompt: int, cached: int | None) -> bool:
    return cached is not None and cached > prompt


def _cache_inconsistent(base_cached: int | None, probe_cached: int | None) -> bool:
    """一侧 cached>0、另一侧为 0 或缺失 → 不可信。两侧都无字段则不查。"""
    if base_cached is None and probe_cached is None:
        return False
    if base_cached is not None and base_cached > 0 and (probe_cached is None or probe_cached == 0):
        return True
    if probe_cached is not None and probe_cached > 0 and (base_cached is None or base_cached == 0):
        return True
    return False


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
