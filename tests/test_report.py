"""报告离线单测：无总分、无密钥、三栏独立，I/D 为 skipped。"""

from __future__ import annotations

import json

from src.report import render_run, write_run_report
from src.types import (
    BankResult,
    Endpoint,
    FamilyResult,
    FamilyScore,
    ProbeDelta,
    QuestionResult,
    SampleGrade,
    Targets,
)


def _ok_family() -> FamilyResult:
    return FamilyResult(
        status="ok",
        family="glm5",
        confidence="high",
        hits=10,
        n_probes=14,
        l1=2,
        runner_up="qwen2_5",
        runner_up_hits=6,
        runner_up_l1=11,
        scores=[
            FamilyScore(catalog_id="glm5", exact_hits=10, l1=2, n_used=14),
            FamilyScore(catalog_id="qwen2_5", exact_hits=6, l1=11, n_used=14),
        ],
        probes=[
            ProbeDelta(
                probe_id="p00",
                text="xx",
                escaped=False,
                prompt_tokens_base=50,
                prompt_tokens_probe=52,
                delta_api=2,
                dropped=False,
                n_hat={"glm5": 2, "qwen2_5": 4},
            )
        ],
    )


def test_report_three_columns_no_total_no_secret(tmp_path):
    run_dir = tmp_path / "run-xxx"
    targets = Targets(
        claimed_model="glm-5.3-flash",
        target=Endpoint(
            base_url="https://example.test/v1",
            api_key_env="TARGET_KEY",
            model="glm-5.3-flash",
        ),
        reference=None,
    )
    write_run_report(
        run_dir,
        targets=targets,
        family=_ok_family(),
        extra={"api_key": "sk-secret", "note": "offline"},
    )

    md = (run_dir / "report.md").read_text(encoding="utf-8")
    report_json = (run_dir / "report.json").read_text(encoding="utf-8")
    family_json = (run_dir / "family.json").read_text(encoding="utf-8")
    blob = md + report_json + family_json

    assert (run_dir / "family.json").is_file()
    assert (run_dir / "report.md").is_file()
    assert (run_dir / "report.json").is_file()

    assert "sk-secret" not in blob
    assert '"api_key"' not in family_json
    assert '"api_key"' not in report_json
    assert "总分" not in blob
    assert "综合分" not in blob
    assert "支持" not in blob
    assert "0–100" not in blob

    assert "- 家族：" in md
    assert "- 判真：skipped" in md
    assert "- 降智：skipped" in md
    assert "流量 / 缓存 / 速率" not in md
    assert "glm5" in md
    assert "10/14" in md
    assert "第二名 qwen2_5" in md
    assert "高" in md
    assert "delta_api" in md
    assert "n_hat" in md

    assert '"identity"' in report_json
    assert '"degrade"' in report_json
    assert '"total"' not in report_json
    assert '"score"' not in report_json.lower() or '"family_scores"' in report_json


def test_render_run_rewrites_md(tmp_path):
    run_dir = tmp_path / "run-abc"
    targets = Targets(
        claimed_model="qwen",
        target=Endpoint(base_url="https://t.test/v1", api_key_env="TARGET_KEY", model="q"),
        reference=Endpoint(base_url="https://r.test/v1", api_key_env="REF_KEY", model="q"),
    )
    write_run_report(run_dir, targets=targets, family=_ok_family())
    (run_dir / "report.md").write_text("stale\n", encoding="utf-8")
    (run_dir / "report.json").write_text("{}\n", encoding="utf-8")

    render_run(run_dir)

    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert md.startswith("# Audit run-abc")
    assert "- 判真：skipped" in md
    assert "- 降智：skipped" in md
    assert "stale" not in md
    report = (run_dir / "report.json").read_text(encoding="utf-8")
    assert "skipped" in report
    assert "sk-" not in report


def test_untrusted_and_ambiguous_bars(tmp_path):
    run_dir = tmp_path / "run-bad"
    targets = {
        "claimed_model": "x",
        "target": {"base_url": "https://t", "api_key_env": "TARGET_KEY", "model": "x"},
        "reference": None,
    }
    write_run_report(
        run_dir,
        targets=targets,
        family=FamilyResult(
            status="token_untrusted",
            family="token_untrusted",
            confidence=None,
            hits=0,
            n_probes=3,
            l1=None,
            runner_up=None,
            runner_up_hits=None,
            runner_up_l1=None,
            untrusted_reason="too_few_valid_probes",
        ),
    )
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "token_untrusted" in md
    assert "支持" not in md

    run_dir2 = tmp_path / "run-amb"
    write_run_report(
        run_dir2,
        targets=targets,
        family=FamilyResult(
            status="ambiguous",
            family="ambiguous",
            confidence=None,
            hits=7,
            n_probes=14,
            l1=4,
            runner_up="qwen2_5",
            runner_up_hits=7,
            runner_up_l1=5,
        ),
    )
    md2 = (run_dir2 / "report.md").read_text(encoding="utf-8")
    assert "ambiguous" in md2
    assert "支持" not in md2


def test_report_bank_domain_rates(tmp_path):
    run_dir = tmp_path / "run-bank"
    targets = Targets(
        claimed_model="x",
        target=Endpoint(base_url="https://t", api_key_env="TARGET_KEY", model="x"),
    )
    bank = BankResult(
        quick=True,
        salt="run-bank",
        questions=[
            QuestionResult(
                question_id="coding-medium-01-python",
                domain="coding",
                difficulty="medium",
                samples=[
                    SampleGrade(
                        temperature=0.0,
                        status="pass",
                        passed=True,
                        detail="POINTS 6/6",
                        points=6,
                        points_total=6,
                        score10=10.0,
                    )
                ],
                pass0=True,
                majority=None,
                score10=10.0,
                construct="code_sandbox",
                question_hash="qh-coding-01",
                fixture_hash="fh-coding-01",
            ),
            QuestionResult(
                question_id="coding-medium-02-python",
                domain="coding",
                difficulty="medium",
                samples=[SampleGrade(temperature=0.0, status="missing", passed=None, detail="no fence")],
                pass0=None,
                majority=None,
            ),
        ],
        domain_pass0={"architecture": {"passed": 6, "judged": 8, "missing": 0}, "coding": {"passed": 1, "judged": 1, "missing": 1}, "knowledge": {"passed": 8, "judged": 8, "missing": 0}, "reasoning": {"passed": 4, "judged": 8, "missing": 0}},
        domain_points={"architecture": {"earned": 0, "total": 0, "score10": None}, "coding": {"earned": 6, "total": 6, "score10": 10.0}, "knowledge": {"earned": 8, "total": 8, "score10": 10.0}, "reasoning": {"earned": 4, "total": 8, "score10": 5.0}},
        difficulty_points={
            "easy": {"passed": 0, "judged": 0, "earned": 0, "total": 0, "score10": None},
            "medium": {"passed": 1, "judged": 1, "earned": 6, "total": 6, "score10": 10.0},
            "hard": {"passed": 0, "judged": 0, "earned": 0, "total": 0, "score10": None},
            "extreme": {"passed": 0, "judged": 1, "earned": 2, "total": 4, "score10": 5.0},
        },
        knowledge_all_wrong=False,
        n_questions=2,
        raw_question_count=50,
        expanded_question_count=74,
        coding_cluster_count=12,
        coding_variant_count=36,
        coding_available={"passed": 10, "judged": 11, "missing": 1, "rate": 0.9091},
        coding_strict={"passed": 8, "judged": 9, "missing": 3, "rate": 0.8889},
        raw_matrix={
            "architecture": {"easy": 1, "medium": 1, "hard": 5, "extreme": 5},
            "coding": {"easy": 1, "medium": 1, "hard": 5, "extreme": 5},
            "knowledge": {"easy": 1, "medium": 1, "hard": 5, "extreme": 5},
            "reasoning": {"easy": 2, "medium": 2, "hard": 5, "extreme": 5},
        },
    )
    write_run_report(run_dir, targets=targets, family=_ok_family(), bank=bank)
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "分域通过率" in md
    assert "分域折合10" in md
    assert "分难度折合10" in md
    assert "architecture 6/8" in md
    assert "coding 1/1" in md
    assert "knowledge 8/8" in md
    assert "reasoning 4/8" in md
    assert "coding 10.0" in md
    assert "knowledge 10.0" in md
    assert "reasoning 5.0" in md
    assert "medium 10.0" in md
    assert "extreme 5.0" in md
    assert "原始题 50 道" in md
    assert "展开题 74 道" in md
    assert "raw cluster 12" in md
    assert "语言变体 36" in md
    assert "编码题可用语言口径：10/11 (0.9091)" in md
    assert "三语齐全口径：8/9 (0.8889)" in md
    assert "architecture 1/1/5/5" in md
    assert "reasoning 2/2/5/5" in md
    assert "score10" in md
    assert "coding-medium-01-python" in md
    assert (run_dir / "bank.json").is_file()
    assert "支持" not in md
    assert "bank_version=bank-v2.1" in md
    assert "scorer_version=scorer-v2" in md
    assert "sampling_protocol=single-v1" in md
    assert "全量（四档，4 次采样）" not in md
    assert "construct" in md
    assert "code_sandbox" in md
    assert "question_hash" in md
    assert "qh-coding-01" in md
    assert "fixture_hash" in md
    assert "fh-coding-01" in md
    assert "missing=1" in md
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["provenance"]["bank_version"] == "bank-v2.1"
    assert report["provenance"]["scorer_version"] == "scorer-v2"
    assert report["provenance"]["sampling_protocol"] == "single-v1"
    assert report["bank"]["bank_version"] == "bank-v2.1"
    assert report["bank"]["scorer_version"] == "scorer-v2"
    assert report["bank"]["sampling_protocol"] == "single-v1"
    q0 = report["bank"]["questions"][0]
    assert q0["construct"] == "code_sandbox"
    assert q0["question_hash"] == "qh-coding-01"
    assert q0["fixture_hash"] == "fh-coding-01"
    assert report["bank"]["domain_pass0"]["coding"]["missing"] == 1


def test_report_full_single_v1_not_labeled_as_four_sample(tmp_path):
    run_dir = tmp_path / "run-full"
    targets = Targets(
        claimed_model="x",
        target=Endpoint(base_url="https://t", api_key_env="TARGET_KEY", model="x"),
    )
    bank = BankResult(
        quick=False,
        salt="run-full",
        questions=[
            QuestionResult(
                question_id="knowledge-easy-01",
                domain="knowledge",
                difficulty="easy",
                samples=[SampleGrade(temperature=0.0, status="pass", passed=True, detail="POINTS 1/1")],
                pass0=True,
                construct="rfc_fact",
                question_hash="qh-k",
                fixture_hash=None,
            )
        ],
        n_questions=1,
        raw_question_count=1,
        expanded_question_count=1,
        sampling_protocol="single-v1",
    )
    write_run_report(run_dir, targets=targets, family=_ok_family(), bank=bank)
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "全量（四档）" in md
    assert "每题 1 次（sampling_protocol=single-v1）" in md
    assert "全量（四档，4 次采样）" not in md
    assert "旧 4 次采样是另一口径，不可混比" in md
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["bank"]["sampling_protocol"] == "single-v1"


def test_report_legacy_bank_does_not_imply_single_v1(tmp_path):
    run_dir = tmp_path / "run-legacy"
    run_dir.mkdir()
    (run_dir / "family.json").write_text(
        json.dumps(
            {
                "target": {"base_url": "https://t", "model": "x", "api_key_env": "TARGET_KEY"},
                "claimed": "x",
                "bank": {"quick": False, "questions": []},
            }
        ),
        encoding="utf-8",
    )
    render_run(run_dir)
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "sampling_protocol=—" in md
    assert "sampling_protocol=single-v1" not in md
    assert "采样协议未标注" in md
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["provenance"]["sampling_protocol"] is None
    assert report["bank"].get("sampling_protocol") is None


def test_report_includes_traffic_from_jsonl(tmp_path):
    run_dir = tmp_path / "run-traffic"
    targets = Targets(
        claimed_model="x",
        target=Endpoint(base_url="https://t", api_key_env="TARGET_KEY", model="x"),
    )
    run_dir.mkdir()
    (run_dir / "requests.jsonl").write_text(
        json.dumps(
            {
                "status_code": 200,
                "prompt_tokens": 80,
                "completion_tokens": 8,
                "latency_ms": 800,
                "usage": {"cached_tokens": 20},
                "metrics": {
                    "billed_prompt_tokens": 60,
                    "e2e_output_tps": 10.0,
                    "input_chars": 16,
                    "output_chars": 4,
                    "cache_hit_ratio": 0.25,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_run_report(run_dir, targets=targets, family=_ok_family())
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    family = (run_dir / "family.json").read_text(encoding="utf-8")
    assert "流量 / 缓存 / 速率" in md
    assert "缓存命中率" in md
    assert "0.25" in md
    assert '"traffic"' in family
    assert "sk-" not in md + family


def test_report_shell_appendix_no_family_column_change(tmp_path):
    from src.envelopes import EnvelopeProbe, EnvelopeResult
    from src.sku import CatalogAbResult, SkuCard, SkuPeerCompare, SkuSignal
    from src.wrapper import WrapperResult

    run_dir = tmp_path / "run-shell"
    targets = Targets(
        claimed_model="glm-5.3-flash",
        target=Endpoint(
            base_url="https://example.test/v1",
            api_key_env="TARGET_KEY",
            model="omen-alpha",
        ),
    )
    write_run_report(
        run_dir,
        targets=targets,
        family=None,
        wrapper=WrapperResult(
            status="constant",
            catalog_id="glm5",
            value=36,
            spread=0,
        ),
        sku=CatalogAbResult(
            status="shell_diff",
            target=SkuCard(
                model_id="omen-alpha",
                hi_prompt_tokens=37,
                emoji_delta=16,
                special_image_delta=1,
                effort_none=SkuSignal(
                    name="effort_none",
                    prompt_tokens=37,
                    delta=None,
                    http=200,
                    kind="accepted",
                    detail=None,
                ),
                signals=[],
                error=None,
            ),
            peers=[
                SkuPeerCompare(
                    peer_id="glm-5.3-flash",
                    wrapper_offset=24,
                    emoji_delta_peer=16,
                    special_image_delta_peer=7,
                    effort_none_kind="zhipu_numeric",
                    same_emoji=True,
                    same_effort_kind=False,
                    note="壳差 24，不能证明是同一条权重",
                )
            ],
            cards=[],
            note="相对具名对照多出固定壳",
        ),
        envelopes=EnvelopeResult(
            status="ok",
            family="rust_serde",
            probes=[
                EnvelopeProbe(
                    name="temperature_wrong_type",
                    http=400,
                    kind="serde",
                    detail="expected f32",
                    prompt_tokens=None,
                )
            ],
            note="",
        ),
    )
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    family_json = (run_dir / "family.json").read_text(encoding="utf-8")
    report_json = (run_dir / "report.json").read_text(encoding="utf-8")
    blob = md + family_json + report_json
    assert "（本 run 未跑 F）" in md
    assert "- 判真：skipped" in md
    assert "壳 / 适配器" in md
    assert "wrapper：constant glm5 +36" in md
    assert "sku：shell_diff hi=37" in md
    assert "offset=+24" in md
    assert "envelopes：rust_serde" in md
    assert "支持" not in blob
    assert "总分" not in blob
    assert '"wrapper"' in family_json
    assert '"sku"' in report_json
