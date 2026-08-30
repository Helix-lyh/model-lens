"""报告离线单测：无总分、无密钥、三栏独立，I/D 为 skipped。"""

from __future__ import annotations

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
        domain_pass0={"architecture": {"passed": 6, "judged": 8, "missing": 0}, "coding": {"passed": 1, "judged": 1, "missing": 1}, "knowledge": {"passed": 8, "judged": 8, "missing": 0}},
        domain_points={"architecture": {"earned": 0, "total": 0, "score10": None}, "coding": {"earned": 6, "total": 6, "score10": 10.0}, "knowledge": {"earned": 8, "total": 8, "score10": 10.0}},
        difficulty_points={"easy": {"passed": 0, "judged": 0, "earned": 0, "total": 0, "score10": None}, "medium": {"passed": 1, "judged": 1, "earned": 6, "total": 6, "score10": 10.0}, "hard": {"passed": 0, "judged": 0, "earned": 0, "total": 0, "score10": None}},
        knowledge_all_wrong=False,
        n_questions=2,
    )
    write_run_report(run_dir, targets=targets, family=_ok_family(), bank=bank)
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "分域通过率" in md
    assert "分域折合10" in md
    assert "分难度折合10" in md
    assert "coding 1/1" in md
    assert "coding 10.0" in md
    assert "medium 10.0" in md
    assert "score10" in md
    assert "coding-medium-01-python" in md
    assert (run_dir / "bank.json").is_file()
    assert "支持" not in md


def test_report_includes_traffic_from_jsonl(tmp_path):
    import json

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
