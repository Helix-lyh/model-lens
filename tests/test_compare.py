from __future__ import annotations

from src.catalog import lookup_claimed_family
from src.compare import (
    coding_agreement,
    confidence_for_identity,
    decide_degrade,
    decide_identity,
    same_gateway,
)
from src.types import (
    BankResult,
    Endpoint,
    FamilyResult,
    IdentityResult,
    ProbeDelta,
    QuestionResult,
    SampleGrade,
    Targets,
)


def _family(**kwargs) -> FamilyResult:
    probes = kwargs.pop("probes", None)
    if probes is None:
        probes = [
            ProbeDelta(
                probe_id="p",
                text="x",
                escaped=False,
                prompt_tokens_base=10,
                prompt_tokens_probe=12,
                delta_api=2,
                dropped=False,
            )
        ]
    return FamilyResult(
        status=kwargs.get("status", "ok"),
        family=kwargs.get("family", "glm5"),
        confidence=kwargs.get("confidence", "high"),
        hits=kwargs.get("hits", 10),
        n_probes=kwargs.get("n_probes", 14),
        l1=kwargs.get("l1", 2),
        runner_up=kwargs.get("runner_up", "qwen2_5"),
        runner_up_hits=6,
        runner_up_l1=11,
        probes=probes,
        untrusted_reason=kwargs.get("untrusted_reason"),
    )


def _targets(claimed="glm-5.3-flash", ref=True, same=False) -> Targets:
    target = Endpoint(
        base_url="https://gw.example/v1",
        api_key_env="TARGET_KEY",
        model="glm-5.3-flash",
        channel="newapi",
    )
    reference = None
    if ref:
        url = "https://gw.example/v1" if same else "https://open.bigmodel.cn/api/paas/v4"
        reference = Endpoint(
            base_url=url,
            api_key_env="REF_KEY",
            model="glm-5.3-flash",
            channel="zhipu" if not same else "newapi",
        )
    return Targets(claimed_model=claimed, target=target, reference=reference)


def _coding_bank(pass0s: list[bool | None], majority: list[bool | None] | None = None) -> BankResult:
    qs = []
    for i, p0 in enumerate(pass0s):
        maj = None if majority is None else majority[i]
        qs.append(
            QuestionResult(
                question_id=f"B0{i+1}",
                domain="coding",
                pass0=p0,
                majority=maj,
                samples=[SampleGrade(0.0, "pass" if p0 else "fail", p0, "x")],
            )
        )
    judged = [x for x in pass0s if x is not None]
    return BankResult(
        quick=majority is None,
        salt="t",
        questions=qs,
        domain_pass0={
            "coding": {
                "passed": sum(1 for x in judged if x),
                "judged": len(judged),
                "missing": sum(1 for x in pass0s if x is None),
            }
        },
    )


def _coding_variant_bank(
    rows: list[tuple[str, str, bool | None]],
    *,
    metadata: bool = True,
) -> BankResult:
    questions = []
    for cluster, language, passed in rows:
        status = "pass" if passed is True else "fail" if passed is False else "missing"
        questions.append(
            QuestionResult(
                question_id=f"{cluster}-{language}",
                domain="coding",
                pass0=passed,
                majority=passed,
                language=language if metadata else None,
                raw_id=cluster if metadata else None,
                cluster_id=cluster if metadata else None,
                samples=[SampleGrade(0.0, status, passed, "x")],
            )
        )
    return BankResult(quick=False, salt="t", questions=questions)


def test_lookup_longest_prefix() -> None:
    assert lookup_claimed_family("glm-5.3-flash") == "glm5"
    assert lookup_claimed_family("qwen3-8b") == "qwen2_5"
    assert lookup_claimed_family("qwen3.8-flash-next") == "qwen3_8"
    assert lookup_claimed_family("totally-unknown-model") is None


def test_untrusted_skips_identity() -> None:
    i = decide_identity(
        _family(status="token_untrusted", family="token_untrusted", confidence=None),
        _targets(),
        claimed_family="glm5",
    )
    assert i.status == "skipped"
    assert "token_untrusted" in i.note


def test_no_reference_skips_identity() -> None:
    i = decide_identity(
        _family(family="qwen2_5", confidence="high"),
        _targets(ref=False),
        claimed_family="glm5",
    )
    assert i.status == "skipped"
    assert i.note == "无参考源"


def test_unregistered_claimed() -> None:
    i = decide_identity(_family(), _targets(claimed="mystery"), claimed_family=None)
    assert i.status == "skipped"
    assert i.note == "未登记家族"


def test_same_gateway_invalid() -> None:
    t = _targets(same=True)
    assert same_gateway(t.target, t.reference)
    i = decide_identity(_family(), t, claimed_family="glm5")
    assert i.status == "invalid"


def test_cross_family_not_supported() -> None:
    t = _targets()
    assert t.reference is not None
    i = decide_identity(
        _family(family="qwen2_5", confidence="medium"),
        t,
        claimed_family="glm5",
    )
    assert i.status == "不支持"
    assert i.observed_family == "qwen2_5"
    assert "支持" not in i.note or i.status != "支持"


def test_ambiguous_does_not_cross() -> None:
    i = decide_identity(
        _family(status="ambiguous", family="ambiguous", confidence=None),
        _targets(),
        claimed_family="glm5",
    )
    assert i.status == "skipped"


def test_same_family_untyped() -> None:
    i = decide_identity(_family(family="glm5"), _targets(), claimed_family="glm5")
    assert i.status == "同族未分型"


def test_low_confidence_conflict_skips() -> None:
    i = decide_identity(
        _family(family="qwen2_5", confidence="low"),
        _targets(),
        claimed_family="glm5",
    )
    assert i.status == "skipped"
    assert "置信不足" in i.note


def test_gateway_caps_high_unless_usage_ok() -> None:
    dropped = [
        ProbeDelta("p", "x", False, 10, 12, 2, True, drop_reason="no usage"),
    ]
    fam = _family(confidence="high", probes=dropped, status="ok")
    ep = _targets().target
    assert confidence_for_identity(fam, ep, usage_ok=False) == "medium"
    assert confidence_for_identity(_family(confidence="high"), ep, usage_ok=True) == "high"


def test_gateway_alias_caps_high_when_usage_inconsistent() -> None:
    dropped = [
        ProbeDelta("p", "x", False, 10, 12, 2, True, drop_reason="no usage"),
    ]
    fam = _family(confidence="high", probes=dropped, status="ok")
    for alias in ("new-api", "openai-compat"):
        ep = Endpoint(
            base_url="https://gw.example/v1",
            api_key_env="TARGET_KEY",
            model="glm-5.3-flash",
            channel=alias,
        )
        assert confidence_for_identity(fam, ep, usage_ok=False) == "medium", alias


def test_degrade_quick_skipped() -> None:
    ident = IdentityResult("同族未分型", "glm5", "glm5", "high", "x")
    d = decide_degrade(
        ident, _family(), _targets(), _coding_bank([True]), _coding_bank([True]), quick=True
    )
    assert d.status == "skipped"


def test_degrade_cross_family_skipped() -> None:
    ident = IdentityResult("不支持", "glm5", "qwen2_5", "high", "换货")
    d = decide_degrade(
        ident, _family(), _targets(), _coding_bank([True] * 8), _coding_bank([True] * 8), quick=False
    )
    assert d.status == "skipped"
    assert "换货" in d.note or "换家族" in d.note


def test_degrade_single_sample_uses_pass0_as_stab() -> None:
    ident = IdentityResult("同族未分型", "glm5", "glm5", "high", "x")
    target = _coding_bank([False] * 8)
    ref = _coding_bank([True] * 8)
    d = decide_degrade(ident, _family(), _targets(), target, ref, quick=False)
    assert d.status == "疑似衰减"
    assert d.stab_target == 0.0
    assert d.stab_ref == 1.0


def test_degrade_suspected() -> None:
    ident = IdentityResult("同族未分型", "glm5", "glm5", "high", "x")
    target = _coding_bank([False] * 8, [False] * 8)
    ref = _coding_bank([True] * 8, [True] * 8)
    d = decide_degrade(ident, _family(), _targets(), target, ref, quick=False)
    assert d.status == "疑似衰减"
    assert d.pass0_delta is not None and d.pass0_delta >= 0.25
    assert d.stab_delta is not None and d.stab_delta >= 0.20


def test_degrade_score10_gap_without_pass0() -> None:
    ident = IdentityResult("同族未分型", "glm5", "glm5", "high", "x")
    target = _coding_bank([True] * 8, [True] * 8)
    ref = _coding_bank([True] * 8, [True] * 8)
    for q in target.questions:
        q.score10 = 2.0
    for q in ref.questions:
        q.score10 = 9.0
    d = decide_degrade(ident, _family(), _targets(), target, ref, quick=False)
    assert d.status == "疑似衰减"
    assert d.score10_delta is not None and d.score10_delta >= 2.5


def test_degrade_not_detected() -> None:
    ident = IdentityResult("同族未分型", "glm5", "glm5", "high", "x")
    both = _coding_bank([True] * 8, [True] * 8)
    d = decide_degrade(ident, _family(), _targets(), both, both, quick=False)
    assert d.status == "未检出衰减"


def test_degrade_insufficient() -> None:
    ident = IdentityResult("同族未分型", "glm5", "glm5", "high", "x")
    # pass0 差 0.25 但 stab 只差 0.125，未同时破线
    target = _coding_bank(
        [True] * 6 + [False] * 2,
        [True] * 7 + [False],
    )
    ref = _coding_bank([True] * 8, [True] * 8)
    d = decide_degrade(ident, _family(), _targets(), target, ref, quick=False)
    assert d.status == "偏离不足以下结论"


def test_coding_agree_appendix_only() -> None:
    t = _coding_bank([True, False, True])
    r = _coding_bank([True, True, True])
    block = coding_agreement(t, r)
    assert block is not None
    assert block["agree"] == 2
    assert "支持" in block["note"]  # 文案写明不把 I 推成支持


def test_coding_agreement_merges_languages_and_keeps_strict_complete_case() -> None:
    target = _coding_variant_bank(
        [
            ("coding-hard-01", "python", True),
            ("coding-hard-01", "go", True),
            ("coding-hard-01", "typescript", None),
            ("coding-hard-02", "python", True),
            ("coding-hard-02", "go", False),
            ("coding-hard-02", "typescript", True),
            ("coding-hard-03", "python", None),
            ("coding-hard-03", "go", None),
            ("coding-hard-03", "typescript", None),
        ]
    )
    reference = _coding_variant_bank(
        [
            ("coding-hard-01", "python", True),
            ("coding-hard-01", "go", True),
            ("coding-hard-01", "typescript", True),
            ("coding-hard-02", "python", True),
            ("coding-hard-02", "go", True),
            ("coding-hard-02", "typescript", True),
            ("coding-hard-03", "python", None),
            ("coding-hard-03", "go", None),
            ("coding-hard-03", "typescript", None),
        ]
    )
    block = coding_agreement(target, reference)
    assert block == {
        "compared": 2,
        "agree": 1,
        "rate": 0.5,
        "clusters": 3,
        "strict_compared": 1,
        "strict_agree": 0,
        "strict_rate": 0.0,
        "strict_clusters": 3,
        "note": "按 coding raw cluster 比较，只进附录，不把 I 推成「支持」；strict 只纳入三语均已判定的 cluster",
    }


def test_coding_agreement_legacy_language_suffix_fallback() -> None:
    rows = [
        ("coding-extreme-01", "python", True),
        ("coding-extreme-01", "go", True),
        ("coding-extreme-01", "typescript", True),
    ]
    block = coding_agreement(
        _coding_variant_bank(rows, metadata=False),
        _coding_variant_bank(rows, metadata=False),
    )
    assert block is not None
    assert block["clusters"] == 1
    assert block["compared"] == 1
    assert block["strict_clusters"] == 1
    assert block["strict_compared"] == 1
    assert block["strict_rate"] == 1.0
