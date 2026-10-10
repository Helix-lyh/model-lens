"""summary.md 按渠道拆分、截断按固定分母记 0。"""
from __future__ import annotations

from cursor_workspace.build_scripts import run_eval_20260925 as run_eval
from eval_bank_20260925.evaluation import summarize, summarize_engineering
from eval_bank_20260925.report import render_markdown


def _row(channel, item, status, points=None, **extra):
    bank = {"CP": "business-coding", "E": "business-engineering", "NX": "business-reasoning"}[item.split("-")[0]]
    row = {"channel": channel, "experiment_id": "run", "item": item, "lang": None, "sample": 0,
           "bank_id": bank, "bank_version": "v", "status": status, "points": points, "points_total": 20,
           "passed": {"pass": True, "fail": False}.get(status), "score10": None if points is None else points / 2,
           "score_percent": None if points is None else points * 5.0}
    row.update(extra)
    return row


TRUNC = {"reason_code": "response_truncated", "truncated": True, "finish_reason": "length"}


def test_truncation_counts_as_zero_in_fixed_denominator():
    rows = [_row("a", "NX-09", "pass", 20, reason_code="ok"), _row("a", "NX-10", "error", **TRUNC)]
    stats = summarize(rows)
    assert stats["points_total"] == 40
    assert stats["score_percent_total"] == 50.0
    assert stats["judged_score_percent_total"] == 100.0
    assert stats["truncated"] == 1
    assert stats["mean_percent"] == 50.0


def test_engineering_truncation_counts_as_zero():
    rows = [
        _row("a", "E-01", "fail", 10, positive_points=12, negative_points=2, net_points=10, reason_code="content_mismatch"),
        _row("a", "E-02", "error", **TRUNC),
    ]
    stats = summarize_engineering(rows)
    assert stats["net_percent_total"] == 25.0
    assert stats["judged_net_percent_total"] == 50.0
    assert stats["truncated"] == 1


def test_summary_markdown_splits_channels_and_matches_summary_json():
    rows = [
        _row("a", "CP-09", "pass", 20, reason_code="ok"),
        _row("b", "CP-09", "error", **TRUNC),
    ]
    text = render_markdown({"experiment_id": "t", "models": ["a", "b"], "samples": 1}, rows)
    assert "## 渠道 a" in text and "## 渠道 b" in text
    section_a = text[text.index("## 渠道 a"):text.index("## 渠道 b")]
    section_b = text[text.index("## 渠道 b"):text.index("## 逐题")]
    assert "| coding | 1/1 | 20 | 20 | 100.0% |" in section_a
    assert "| coding | 0/1 | 0 | 20 | 0.0% |" in section_b
    assert "截断（0分）" in text
    summary = run_eval.summarize(rows, ["a", "b"])
    assert summary["a"]["coding"]["score_percent_total"] == 100.0
    assert summary["b"]["coding"]["score_percent_total"] == 0.0
