"""统一题库评测合同。

题面可以有不同输入/输出协议，但执行器只依赖这里的四个边界：
题目分派、评分、超时归一化、汇总。默认活动配置只包含 20261008 的三栏。
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from typing import Any, Callable


JUDGED_STATUSES = frozenset({"pass", "fail"})
NON_JUDGED_STATUSES = frozenset({"error", "missing", "pending_review"})


def _score_item(item: Any, text: str, *, language: str | None = None) -> dict[str, Any]:
    """Dispatch through the bank's registered adapter, then validate its contract."""
    from .bank_adapters import score_item_with_adapter

    result = score_item_with_adapter(item, text, language)
    return normalize_verdict(result)


def scoring_provenance(item: Any, language: str | None = None) -> dict[str, str | None]:
    """Identify the selected adapter and the implementation used to judge a row."""
    from .bank_adapters import adapter_id_for, scorer_fingerprint

    from .runtime_profiles import profile_provenance

    return {
        "adapter_id": adapter_id_for(item),
        "scorer_sha256": scorer_fingerprint(item),
        **profile_provenance(item.id, language),
    }


def score_item(item: Any, text: str, *, language: str | None = None) -> dict[str, Any]:
    try:
        return _score_item(item, text, language=language)
    except Exception as exc:
        return {"status": "error", "reason_code": "scorer_error", "passed": None,
                "points": None, "score10": None, "detail": repr(exc)}


def unjudged_execution(grade: Any) -> dict[str, Any] | None:
    """Keep missing toolchains and fixture failures outside model ledgers."""
    if grade.status not in {"missing", "error"}:
        return None
    reason = "grader_error" if grade.status == "error" else "missing_toolchain" if "toolchain" in grade.detail else "missing_fence"
    return {"status": grade.status, "reason_code": reason, "passed": None,
            "points": None, "score10": None, "detail": grade.detail}


def _as_dict(verdict: Any) -> dict[str, Any]:
    if isinstance(verdict, dict):
        return dict(verdict)
    if is_dataclass(verdict):
        return asdict(verdict)
    raise TypeError("scorer must return a mapping or dataclass")


def normalize_verdict(verdict: Any, *, points_total: float = 20) -> dict[str, Any]:
    """Validate the shared result fields and return a defensive copy.

    A scorer contract violation is an infrastructure error, never a model
    failure. This prevents invalid points or contradictory pass flags from
    entering a denominator silently.
    """
    raw = _as_dict(verdict)
    status = raw.get("status")
    reason = raw.get("reason_code")
    if status not in JUDGED_STATUSES | NON_JUDGED_STATUSES:
        raise ValueError(f"invalid verdict status: {status!r}")
    if not isinstance(reason, str) or not reason:
        raise ValueError("verdict reason_code must be a non-empty string")
    passed = raw.get("passed")
    if status == "pass" and passed is not True:
        raise ValueError("pass verdict must have passed=True")
    if status == "fail" and passed is not False:
        raise ValueError("fail verdict must have passed=False")
    if status not in JUDGED_STATUSES and passed is not None:
        raise ValueError("non-judged verdict must have passed=None")
    points = raw.get("points")
    score10 = raw.get("score10")
    for name, value in (("points", points), ("score10", score10)):
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value))):
            raise ValueError(f"verdict {name} must be finite numeric or None")
    total = raw.get("points_total", points_total)
    if type(total) not in (int, float) or not math.isfinite(total) or total <= 0:
        raise ValueError("verdict points_total must be finite and positive")
    ledger = raw.get("net_points") is not None
    lower_bound = -total if ledger else 0
    if points is not None and not lower_bound <= points <= total:
        raise ValueError("verdict points out of range")
    if score10 is not None and not 0 <= score10 <= 10:
        raise ValueError("verdict score10 out of range")
    if ledger:
        positive, negative, net = (raw.get(field) for field in ("positive_points", "negative_points", "net_points"))
        if any(type(value) is not int or not 0 <= value <= total for value in (positive, negative)):
            raise ValueError("verdict engineering ledger out of range")
        if type(net) is not int or net != positive - negative or points != net or score10 is not None:
            raise ValueError("verdict engineering ledger disagrees")
        if positive + negative > total:
            raise ValueError("verdict engineering observations exceed total")
    if status in JUDGED_STATUSES and (points is None or not ledger and score10 is None):
        raise ValueError("judged verdict requires points and score10")
    if points is not None and score10 is not None and abs(float(score10) - 10 * float(points) / total) > 1e-4:
        raise ValueError("verdict points and score10 disagree")
    if status == "pass" and (points != total or raw.get("protocol_ok") is False):
        raise ValueError("pass verdict requires full points and valid protocol")
    if status in NON_JUDGED_STATUSES and (points is not None or score10 is not None):
        raise ValueError("non-judged verdict must not contain a score")
    raw.setdefault("points_total", total)
    _attach_percent(raw, total)
    return raw


def _attach_percent(raw: dict[str, Any], total: float) -> None:
    """阶段分和题目分都换成该分母上的百分数。工程净分可以是负数。"""
    points = raw.get("points")
    if isinstance(points, (int, float)) and not isinstance(points, bool):
        raw["score_percent"] = round(100.0 * float(points) / float(total), 1)
    if raw.get("net_points") is not None:
        raw["positive_percent"] = round(100.0 * raw["positive_points"] / float(total), 1)
        raw["negative_percent"] = round(100.0 * raw["negative_points"] / float(total), 1)
    groups = raw.get("groups")
    if not isinstance(groups, list):
        return
    copied = []
    for group in groups:
        if isinstance(group, dict):
            group = dict(group)
            maximum = group.get("max")
            got = group.get("points")
            if (
                isinstance(maximum, (int, float)) and not isinstance(maximum, bool) and maximum
                and isinstance(got, (int, float)) and not isinstance(got, bool)
            ):
                group["percent"] = round(100.0 * float(got) / float(maximum), 1)
        copied.append(group)
    raw["groups"] = copied


def is_timeout_error(error: str | None, status_code: int | None = None) -> bool:
    text = (error or "").lower()
    return status_code == 408 or any(token in text for token in ("timed out", "timeout", "readtimeout", "deadline exceeded"))


def _timeout_zero(item: Any, detail: Any) -> dict[str, Any]:
    """An empty timed-out answer is a judged zero, including the engineering ledger."""
    item_id = str(getattr(item, "id", "") or "")
    verdict: dict[str, Any] = {
        "status": "fail",
        "reason_code": "timeout",
        "passed": False,
        "points": 0,
        "points_total": 20,
        "detail": detail,
    }
    if item_id.startswith("E-"):
        verdict.update(score10=None, positive_points=0, negative_points=0, net_points=0)
    else:
        verdict["score10"] = 0.0
    return verdict


def timeout_verdict(
    item: Any,
    text: str,
    *,
    language: str | None = None,
    scorer: Callable[[Any, str], Any] | None = None,
) -> dict[str, Any]:
    """Turn every timeout into a judged failure.

    Empty output is zero. A structurally parseable partial response keeps the
    points returned by the item's normal grouped scorer, but can never pass.
    Request errors that are not timeouts must not call this function.
    """
    try:
        verdict = normalize_verdict(scorer(item, text) if scorer else score_item(item, text, language=language))
    except Exception as exc:
        return {"status": "error", "reason_code": "scorer_error", "passed": None,
                "points": None, "score10": None, "detail": repr(exc)}
    if not is_judged(verdict):
        # 请求已经超时。抽不出正文是这次作答的 0 分，不是缺工具链。
        reason = str(verdict.get("reason_code") or "")
        detail = str(verdict.get("detail") or "")
        infrastructure = (
            verdict.get("status") == "error"
            or reason in {"scorer_error", "grader_error", "runtime_error", "runtime_missing", "missing_toolchain"}
            or "toolchain" in reason
            or "toolchain" in detail
        )
        if infrastructure:
            return verdict
        return normalize_verdict(_timeout_zero(item, verdict.get("detail")))
    points = verdict["points"]
    verdict["status"] = "fail"
    verdict["passed"] = False
    verdict["points"] = points
    verdict["reason_code"] = "timeout_partial" if points or verdict.get("positive_points") or verdict.get("negative_points") else "timeout"
    return verdict


def is_judged(row: dict[str, Any]) -> bool:
    return row.get("status") in JUDGED_STATUSES


def pass_at_k(rows: list[dict[str, Any]], k: int, *, key_fields: tuple[str, ...] = ("item", "lang")) -> tuple[float | None, int, int]:
    """Estimate within one experiment, channel and immutable item revision.

    Legacy rows without sample identity are readable, but cannot provide a
    uniqueness guarantee. Newly emitted rows always include experiment/sample.
    """
    if k < 1:
        raise ValueError("pass_at_k requires k >= 1")
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    seen_samples: set[tuple[Any, ...]] = set()
    for row in rows:
        if row.get("item"):
            provenance = tuple(row.get(field) for field in (
                "channel", "model", "bank_id", "bank_version", "base_prompt_sha256",
                "adapter_id", "scorer_sha256", "runtime_profile_id", "runtime_profile_sha256",
            ))
            scope = row.get("experiment_id") or row.get("run_id")
            key = (scope,) + provenance + tuple(row.get(field) for field in key_fields)
            sample = row.get("sample")
            sample_key = key + (sample,) if sample is not None else None
            if sample_key is not None and sample_key in seen_samples:
                raise ValueError(f"duplicate logical sample: {sample_key!r}")
            if sample_key is not None:
                seen_samples.add(sample_key)
            grouped[key].append(row)
    estimates: list[float] = []
    eligible = 0
    for samples in grouped.values():
        judged = [row for row in samples if is_judged(row)]
        n = len(judged)
        if n < k:
            continue
        correct = sum(row.get("passed") is True for row in judged)
        estimate = 1.0 if correct == n or n - correct < k else 0.0 if correct == 0 else 1.0 - math.comb(n - correct, k) / math.comb(n, k)
        estimates.append(estimate)
        eligible += 1
    return (round(sum(estimates) / len(estimates), 4) if estimates else None, eligible, len(grouped))


def summarize(rows: list[dict[str, Any]], *, pass_k: int = 1) -> dict[str, Any]:
    """Small shared summary primitive used by bank-specific report renderers."""
    judged = [row for row in rows if is_judged(row)]
    numeric = [row for row in judged if row.get("score10") is not None]
    if any(type(row["score10"]) not in (int, float) or not math.isfinite(row["score10"]) for row in numeric):
        raise ValueError("non-finite or invalid summary score10")
    pass1, eligible1, count = pass_at_k(rows, 1)
    passk, eligiblek, _ = pass_at_k(rows, pass_k)
    earned = sum(float(row.get("points", 0)) for row in judged if row.get("points") is not None)
    possible = sum(float(row.get("points_total", 20)) for row in judged)
    return {
        "attempted": len(rows),
        "attempted_samples": len(rows),
        "questions": count,
        "judged": len(judged),
        "passed": sum(row.get("passed") is True for row in judged),
        "pass_at_1": pass1,
        "pass_at_1_eligible": eligible1,
        "pass_at_k": passk,
        "pass_at_k_eligible": eligiblek,
        "pass_at_k_items": count,
        "pass_k": pass_k,
        "points": earned,
        "points_total": possible,
        "score_percent_total": round(100.0 * earned / possible, 1) if possible else None,
        "group_totals": aggregate_groups(judged),
        "mean_score10": round(sum(float(row["score10"]) for row in numeric) / len(numeric), 4) if numeric else None,
        "mean_percent": _mean_percent(judged),
        "errors": sum(row.get("status") == "error" for row in rows),
        "missing": sum(row.get("status") == "missing" for row in rows),
        "pending_review": sum(row.get("status") == "pending_review" for row in rows),
        "timeouts": sum(row.get("reason_code") in {"timeout", "timeout_partial"} for row in rows),
    }


def summarize_engineering(rows: list[dict[str, Any]], *, pass_k: int = 1) -> dict[str, Any]:
    """Engineering uses signed relation ledgers, never a generic score10."""
    judged = [row for row in rows if is_judged(row)]
    pass1, eligible1, count = pass_at_k(rows, 1)
    passk, eligiblek, _ = pass_at_k(rows, pass_k)
    positive = sum(row.get("positive_points") or 0 for row in judged)
    negative = sum(row.get("negative_points") or 0 for row in judged)
    total = sum(row.get("points_total", 20) for row in judged)
    return {
        "attempted": len(rows), "attempted_samples": len(rows), "questions": count, "judged": len(judged),
        "passed": sum(row.get("passed") is True for row in judged),
        "strict_passed": sum(row.get("passed") is True for row in judged),
        "pass_at_1": pass1, "pass_at_1_eligible": eligible1,
        "pass_at_k": passk, "pass_at_k_eligible": eligiblek,
        "pass_at_k_items": count, "pass_k": pass_k,
        "positive_points": positive, "negative_points": negative,
        "net_points": positive - negative,
        "points_total": total,
        "positive_percent_total": round(100.0 * positive / total, 1) if total else None,
        "negative_percent_total": round(100.0 * negative / total, 1) if total else None,
        "net_percent_total": round(100.0 * (positive - negative) / total, 1) if total else None,
        "group_totals": [],
        "missing": sum(row.get("status") == "missing" for row in rows),
        "errors": sum(row.get("status") == "error" for row in rows),
        "mean_percent": _mean_percent(judged),
    }


def _mean_percent(rows: list[dict[str, Any]]) -> float | None:
    values = [
        float(row["score_percent"])
        for row in rows
        if isinstance(row.get("score_percent"), (int, float)) and not isinstance(row.get("score_percent"), bool)
    ]
    return round(sum(values) / len(values), 1) if values else None


def aggregate_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accumulate same-named scorer groups within one immutable bank revision."""
    totals: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        bank_id = str(row.get("bank_id") or "unscoped")
        bank_version = str(row.get("bank_version") or "unversioned")
        groups = row.get("groups")
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            name, points, maximum = group.get("name"), group.get("points"), group.get("max")
            if (
                not isinstance(name, str) or not name
                or type(points) not in (int, float) or type(maximum) not in (int, float)
                or maximum <= 0 or points < 0 or points > maximum
            ):
                continue
            key = (bank_id, bank_version, name)
            total = totals.setdefault(key, [0.0, 0.0])
            total[0] += float(points)
            total[1] += float(maximum)
    return [
        {
            "bank_id": bank_id,
            "bank_version": version,
            "name": name,
            "points": int(points) if points.is_integer() else points,
            "max": int(maximum) if maximum.is_integer() else maximum,
            "percent": round(100.0 * points / maximum, 1),
        }
        for (bank_id, version, name), (points, maximum) in sorted(totals.items())
    ]
