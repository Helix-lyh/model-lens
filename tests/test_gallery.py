from __future__ import annotations

import json

from src.gallery import build_gallery, write_gallery
from src.reasoning import extract_reasoning
from src.report import write_run_report
from src.types import (
    BankResult,
    Endpoint,
    FamilyResult,
    QuestionResult,
    SampleGrade,
    Targets,
)


def test_extract_reasoning_deepseek_style() -> None:
    data = {
        "choices": [
            {
                "message": {
                    "content": "0",
                    "reasoning_content": "热锅会化糖。",
                }
            }
        ]
    }
    assert extract_reasoning(data) == "热锅会化糖。"


def test_gallery_html_switches_models(tmp_path) -> None:
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    targets_a = Targets(
        claimed_model="deepseek-v4-flash",
        target=Endpoint(base_url="https://a.test", api_key_env="TARGET_KEY", model="deepseek-v4-flash"),
    )
    targets_b = Targets(
        claimed_model="grok-4.5",
        target=Endpoint(base_url="https://b.test", api_key_env="GATEWAY_KEY", model="grok-4.5"),
    )
    bank = BankResult(
        quick=True,
        salt="t",
        questions=[
            QuestionResult(
                question_id="knowledge-easy-01",
                domain="knowledge",
                difficulty="easy",
                samples=[
                    SampleGrade(
                        temperature=0.0,
                        status="pass",
                        passed=True,
                        detail="alias hit=711.90 POINTS 1/1",
                        content="711.90",
                        reasoning="封闭资料的分步计算。",
                        points=1,
                        points_total=1,
                        score10=10.0,
                    )
                ],
                pass0=True,
                score10=10.0,
                construct="rfc_fact",
                question_hash="qh-gallery",
                fixture_hash="fh-gallery",
            )
        ],
        domain_pass0={
            "architecture": {"passed": 0, "judged": 0, "missing": 0},
            "coding": {"passed": 0, "judged": 0, "missing": 0},
            "knowledge": {"passed": 1, "judged": 1, "missing": 0},
            "reasoning": {"passed": 2, "judged": 4, "missing": 0},
        },
        domain_points={
            "architecture": {"earned": 0, "total": 0, "score10": None},
            "coding": {"earned": 0, "total": 0, "score10": None},
            "knowledge": {"earned": 1, "total": 1, "score10": 10.0},
            "reasoning": {"earned": 2, "total": 4, "score10": 5.0},
        },
    )
    write_run_report(
        run_a,
        targets=targets_a,
        family=FamilyResult(
            status="ok",
            family="deepseek_v3",
            confidence="high",
            hits=14,
            n_probes=14,
            l1=0,
            runner_up=None,
            runner_up_hits=None,
            runner_up_l1=None,
        ),
        bank=bank,
        extra={"api_key": "sk-secret"},
    )
    write_run_report(
        run_b,
        targets=targets_b,
        family=FamilyResult(
            status="ambiguous",
            family="ambiguous",
            confidence=None,
            hits=6,
            n_probes=14,
            l1=30,
            runner_up=None,
            runner_up_hits=None,
            runner_up_l1=None,
        ),
        bank=bank,
    )
    out = tmp_path / "gallery"
    html_path = write_gallery([run_a, run_b], out)
    html = html_path.read_text(encoding="utf-8")
    data = (out / "gallery.json").read_text(encoding="utf-8")
    assert "sk-secret" not in html
    assert "sk-secret" not in data
    assert "合成分数" in html
    assert "推理" in html
    assert "reasoning" in html
    assert "支持" not in html
    assert "deepseek-v4-flash" in html
    assert "grok-4.5" in html
    assert "RFC 5952" in html
    assert "711.90" in html
    payload = build_gallery([run_a, run_b])
    assert payload["schema"] == "model-lens.gallery.v1"
    assert len(payload["models"]) == 2
    q0 = payload["models"][0]["questions"][0]
    assert q0["id"] == "knowledge-easy-01"
    assert q0["difficulty"] == "easy"
    assert q0["expected"] == ["见 pass_criteria"]
    assert "711.90" not in q0["expected"]
    assert q0["samples"][0]["answer"] == "711.90"
    assert q0["samples"][0]["reasoning"] == "封闭资料的分步计算。"
    assert q0["samples"][0]["score10"] == 10.0
    assert payload["models"][0]["domain_points"]["knowledge"]["score10"] == 10.0
    assert payload["models"][0]["domains"]["reasoning"]["passed"] == 2
    assert payload["models"][0]["domain_points"]["reasoning"]["score10"] == 5.0
    assert payload["models"][0]["bank_version"] == "20260908"
    assert payload["models"][0]["scorer_version"] == "scorer-v2"
    assert payload["models"][0]["sampling_protocol"] == "single-v1"
    assert q0["construct"] == "rfc_fact"
    assert q0["question_hash"] == "qh-gallery"
    assert q0["fixture_hash"] == "fh-gallery"
    assert '"sampling_protocol": "single-v1"' in data
    assert "rfc_fact" in data
def test_gallery_escapes_dynamic_model_metadata_and_script_terminators(tmp_path) -> None:
    run_dir = tmp_path / "<run-&>"
    malicious = "</script><img src=x onerror=alert(1)>&\"'"
    (run_dir / "family.json").parent.mkdir(parents=True)
    (run_dir / "family.json").write_text(
        __import__("json").dumps(
            {
                "target": {"base_url": "https://example.test", "model": malicious},
                "claimed": malicious,
                "family": {"status": "ok", "family": "glm5", "hits": 1, "n_probes": 1},
                "bank": {
                    "questions": [
                        {
                            "question_id": "knowledge-easy-01",
                            "domain": "knowledge",
                            "difficulty": "easy",
                            "pass0": True,
                            "samples": [{"status": "pass", "passed": True, "content": malicious}],
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "gallery"
    html = write_gallery([run_dir], out).read_text(encoding="utf-8")
    embedded = html.split('<script id="gallery-data" type="application/json">', 1)[1].split("</script>", 1)[0]
    assert "</script>" not in embedded
    assert "<img" not in embedded
    assert "<img src=x onerror" not in embedded
    assert "\\u003cimg src=x onerror" in embedded
    assert "\\u003c/script>" in html
    assert "\\u0026" in html


def test_gallery_legacy_language_suffix_counts_one_cluster(tmp_path) -> None:
    run_dir = tmp_path / "legacy"
    run_dir.mkdir()
    (run_dir / "family.json").write_text(
        __import__("json").dumps(
            {
                "target": {"model": "legacy"},
                "claimed": "legacy",
                "family": {"status": "ok", "family": "glm5", "hits": 1, "n_probes": 1},
                "bank": {
                    "questions": [
                        {"question_id": "coding-hard-01-python", "domain": "coding", "difficulty": "hard"},
                        {"question_id": "coding-hard-01-go", "domain": "coding", "difficulty": "hard"},
                        {"question_id": "coding-hard-01-typescript", "domain": "coding", "difficulty": "hard"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    payload = build_gallery([run_dir])
    model = payload["models"][0]
    assert model["raw_question_count"] == 1
    assert model["coding_cluster_count"] == 1
    assert model["coding_variant_count"] == 3
    assert model["raw_matrix"]["coding"]["hard"] == 1


def test_gallery_reads_bank_json_version_fields(tmp_path) -> None:
    run_dir = tmp_path / "bank-only"
    run_dir.mkdir()
    (run_dir / "bank.json").write_text(
        json.dumps(
            {
                "schema_version": "model-lens.bank.v2",
                "bank_version": "20260908",
                "scorer_version": "scorer-v2",
                "sampling_protocol": "single-v1",
                "questions": [
                    {
                        "question_id": "knowledge-easy-01",
                        "domain": "knowledge",
                        "difficulty": "easy",
                        "construct": "rfc_fact",
                        "question_hash": "aaa",
                        "fixture_hash": "bbb",
                        "pass0": True,
                        "samples": [{"status": "pass", "passed": True, "temperature": 0.0}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    payload = build_gallery([run_dir])
    model = payload["models"][0]
    assert model["schema_version"] == "model-lens.bank.v2"
    assert model["bank_version"] == "20260908"
    assert model["scorer_version"] == "scorer-v2"
    assert model["sampling_protocol"] == "single-v1"
    q0 = model["questions"][0]
    assert q0["construct"] == "rfc_fact"
    assert q0["question_hash"] == "aaa"
    assert q0["fixture_hash"] == "bbb"
