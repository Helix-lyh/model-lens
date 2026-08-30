"""Module I / D。跨族只认 F；同族只标未分型；降智只看编码题。禁止「支持」。"""

from __future__ import annotations

from urllib.parse import urlparse

from src.channels.resolve import resolve_channel
from src.types import (
    BankResult,
    Confidence,
    DegradeResult,
    Endpoint,
    FamilyResult,
    IdentityResult,
    QuestionResult,
    Targets,
)

_CONF_RANK = {"low": 1, "medium": 2, "high": 3}
_GATEWAY_CHANNELS = frozenset({"newapi"})
PASS0_LINE = 0.25
STAB_LINE = 0.20
SMALL = 0.10
SCORE10_LINE = 2.5
SCORE10_SMALL = 1.0
DEGRADE_FOOTNOTE = (
    "8-bit 与同家族弱档经常落在「未检出」。"
    "题库规模可变，二项做 15pp 等价检验功效不够；本工具不假装做成了分布检验。"
)


def same_gateway(target: Endpoint, reference: Endpoint | None) -> bool:
    if reference is None:
        return False
    return _gateway_key(target) == _gateway_key(reference)


def _gateway_key(endpoint: Endpoint) -> str:
    resolved = resolve_channel(endpoint)
    raw = resolved.base_url.rstrip("/").lower()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def usage_self_consistent(family: FamilyResult) -> bool:
    if family.status != "ok":
        return False
    if not family.probes:
        return False
    return all(not p.dropped for p in family.probes)


def confidence_for_identity(
    family: FamilyResult,
    target: Endpoint,
    *,
    usage_ok: bool | None = None,
) -> Confidence | None:
    if family.status != "ok" or family.confidence is None:
        return None
    conf: Confidence = family.confidence
    if usage_ok is None:
        usage_ok = usage_self_consistent(family)
    try:
        channel = resolve_channel(target).channel_id
    except ValueError:
        channel = "newapi"
    if channel in _GATEWAY_CHANNELS and not usage_ok and conf == "high":
        return "medium"
    return conf


def decide_identity(
    family: FamilyResult,
    targets: Targets,
    *,
    claimed_family: str | None,
    bank: BankResult | None = None,
    bank_ref: BankResult | None = None,
) -> IdentityResult:
    coding_agree = coding_agreement(bank, bank_ref)
    if family.status == "token_untrusted":
        return _identity("skipped", claimed_family, None, None, "F=token_untrusted", coding_agree)
    if targets.reference is None:
        return _identity(
            "skipped",
            claimed_family,
            family.family if family.status == "ok" else None,
            family.confidence,
            "无参考源",
            coding_agree,
        )
    if same_gateway(targets.target, targets.reference):
        return _identity(
            "invalid",
            claimed_family,
            family.family if family.status == "ok" else None,
            family.confidence,
            "T/R 同一网关缓存域",
            coding_agree,
        )
    if claimed_family is None:
        return _identity(
            "skipped",
            None,
            family.family if family.status == "ok" else None,
            family.confidence,
            "未登记家族",
            coding_agree,
        )
    if family.status == "ambiguous":
        return _identity("skipped", claimed_family, "ambiguous", None, "F=ambiguous，不猜跨族", coding_agree)

    observed = family.family
    conf = confidence_for_identity(family, targets.target)
    if observed != claimed_family:
        if conf is not None and _CONF_RANK[conf] >= _CONF_RANK["medium"]:
            return _identity("不支持", claimed_family, observed, conf, "跨族换货（只认 F）", coding_agree)
        return _identity(
            "skipped",
            claimed_family,
            observed,
            conf,
            "家族冲突但置信不足，不出「不支持」",
            coding_agree,
        )
    return _identity("同族未分型", claimed_family, observed, conf, "词表同族，分不开 Flash/Pro", coding_agree)


def decide_degrade(
    identity: IdentityResult,
    family: FamilyResult,
    targets: Targets,
    bank: BankResult | None,
    bank_ref: BankResult | None,
    *,
    quick: bool,
    force: bool = False,
) -> DegradeResult:
    skipped = _degrade_precheck(
        identity, family, targets, bank, bank_ref, quick=quick, force=force
    )
    if skipped is not None:
        return skipped

    p0_t = _coding_pass0(bank)
    p0_r = _coding_pass0(bank_ref)
    st_t = _coding_stab(bank)
    st_r = _coding_stab(bank_ref)
    s10_t = _coding_score10(bank)
    s10_r = _coding_score10(bank_ref)
    if p0_t is None or p0_r is None:
        return _degrade("skipped", "编码题有效样本不足", p0_t, p0_r, st_t, st_r, s10_t, s10_r)
    if st_t is None or st_r is None:
        return _degrade("skipped", "无 4 次采样，算不了 stab", p0_t, p0_r, st_t, st_r, s10_t, s10_r)

    d0 = p0_r - p0_t
    ds = st_r - st_t
    d10 = None if s10_t is None or s10_r is None else s10_r - s10_t
    status, note = _degrade_verdict(d0, ds, d10)
    return DegradeResult(
        status=status,
        pass0_target=p0_t,
        pass0_ref=p0_r,
        stab_target=st_t,
        stab_ref=st_r,
        pass0_delta=round(d0, 4),
        stab_delta=round(ds, 4),
        note=note,
        score10_target=s10_t,
        score10_ref=s10_r,
        score10_delta=None if d10 is None else round(d10, 4),
    )


def _degrade_verdict(
    d0: float, ds: float, d10: float | None
) -> tuple[str, str]:
    pass_hit = d0 >= PASS0_LINE and ds >= STAB_LINE
    score_hit = d10 is not None and d10 >= SCORE10_LINE
    small = d0 < SMALL and ds < SMALL and (d10 is None or d10 < SCORE10_SMALL)
    if pass_hit or score_hit:
        return "疑似衰减", _delta_note(d0, ds, d10) + "。" + DEGRADE_FOOTNOTE
    if small:
        return "未检出衰减", DEGRADE_FOOTNOTE
    return "偏离不足以下结论", _delta_note(d0, ds, d10) + "，未同时破线。" + DEGRADE_FOOTNOTE


def _delta_note(d0: float, ds: float, d10: float | None) -> str:
    note = f"pass0Δ={d0:.2f} stabΔ={ds:.2f}"
    if d10 is not None:
        note += f" score10Δ={d10:.2f}"
    return note


def coding_agreement(bank: BankResult | None, bank_ref: BankResult | None) -> dict | None:
    if bank is None or bank_ref is None:
        return None
    t = {q.question_id: q.pass0 for q in bank.questions if q.domain == "coding"}
    r = {q.question_id: q.pass0 for q in bank_ref.questions if q.domain == "coding"}
    ids = sorted(set(t) & set(r))
    both = [i for i in ids if t[i] is not None and r[i] is not None]
    agree = sum(1 for i in both if t[i] == r[i])
    return {
        "compared": len(both),
        "agree": agree,
        "rate": round(agree / len(both), 4) if both else None,
        "note": "只进附录，不把 I 推成「支持」",
    }


def _degrade_precheck(
    identity: IdentityResult,
    family: FamilyResult,
    targets: Targets,
    bank: BankResult | None,
    bank_ref: BankResult | None,
    *,
    quick: bool,
    force: bool,
) -> DegradeResult | None:
    if quick:
        return _degrade("skipped", "--quick 不出降智")
    if family.status in {"token_untrusted", "ambiguous"}:
        return _degrade("skipped", f"F={family.status}")
    if targets.reference is None or bank_ref is None:
        return _degrade("skipped", "无不同网关参考源")
    if same_gateway(targets.target, targets.reference):
        return _degrade("skipped", "T/R 同网关")
    if identity.status == "不支持" and not force:
        return _degrade("skipped", "换家族报换货，不报降智")
    if identity.status != "同族未分型" and not force:
        return _degrade("skipped", f"I={identity.status}")
    if bank is None:
        return _degrade("skipped", "无 target 题库")
    return None


def _coding_qs(bank: BankResult) -> list[QuestionResult]:
    return [q for q in bank.questions if q.domain == "coding"]


def _coding_pass0(bank: BankResult) -> float | None:
    judged = [q.pass0 for q in _coding_qs(bank) if q.pass0 is not None]
    if not judged:
        return None
    return sum(1 for x in judged if x) / len(judged)


def _coding_stab(bank: BankResult) -> float | None:
    qs = [q for q in _coding_qs(bank) if q.majority is not None]
    if not qs:
        return None
    return sum(1 for q in qs if q.majority) / len(qs)


def _coding_score10(bank: BankResult) -> float | None:
    scores = [q.score10 for q in _coding_qs(bank) if q.score10 is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 4)


def _identity(
    status: str,
    claimed: str | None,
    observed: str | None,
    conf: Confidence | None,
    note: str,
    coding_agree: dict | None,
) -> IdentityResult:
    return IdentityResult(
        status=status,  # type: ignore[arg-type]
        claimed_family=claimed,
        observed_family=observed,
        confidence_used=conf,
        note=note,
        coding_agree=coding_agree,
    )


def _degrade(
    status: str,
    note: str,
    p0_t: float | None = None,
    p0_r: float | None = None,
    st_t: float | None = None,
    st_r: float | None = None,
    s10_t: float | None = None,
    s10_r: float | None = None,
) -> DegradeResult:
    d0 = None if p0_t is None or p0_r is None else round(p0_r - p0_t, 4)
    ds = None if st_t is None or st_r is None else round(st_r - st_t, 4)
    d10 = None if s10_t is None or s10_r is None else round(s10_r - s10_t, 4)
    return DegradeResult(
        status=status,  # type: ignore[arg-type]
        pass0_target=p0_t,
        pass0_ref=p0_r,
        stab_target=st_t,
        stab_ref=st_r,
        pass0_delta=d0,
        stab_delta=ds,
        note=note,
        score10_target=s10_t,
        score10_ref=s10_r,
        score10_delta=d10,
    )
