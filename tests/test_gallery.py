from __future__ import annotations

from src.gallery import build_gallery, write_gallery
from src.reasoning import extract_reasoning
from src.report import write_family_report
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
                        detail="alias hit=0 POINTS 1/1",
                        content="0",
                        reasoning="冰糖会化。",
                        points=1,
                        points_total=1,
                        score10=10.0,
                    )
                ],
                pass0=True,
                score10=10.0,
            )
        ],
        domain_pass0={"knowledge": {"passed": 1, "judged": 1, "missing": 0}},
        domain_points={"knowledge": {"earned": 1, "total": 1, "score10": 10.0}},
    )
    write_family_report(
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
    write_family_report(
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
    assert "支持" not in html
    assert "deepseek-v4-flash" in html
    assert "grok-4.5" in html
    assert "热锅" in html or "完整冰糖" in html
    assert "冰糖会化" in html
    payload = build_gallery([run_a, run_b])
    assert payload["schema"] == "model-lens.gallery.v1"
    assert len(payload["models"]) == 2
    q0 = payload["models"][0]["questions"][0]
    assert q0["id"] == "knowledge-easy-01"
    assert q0["difficulty"] == "easy"
    assert q0["samples"][0]["answer"] == "0"
    assert q0["samples"][0]["reasoning"] == "冰糖会化。"
    assert q0["samples"][0]["score10"] == 10.0
    assert payload["models"][0]["domain_points"]["knowledge"]["score10"] == 10.0
    assert (run_a / "gallery.json").is_file()
