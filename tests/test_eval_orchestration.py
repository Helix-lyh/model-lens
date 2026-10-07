from __future__ import annotations

import json
import sys
from pathlib import Path

from src.types import CompletionRecord

from cursor_workspace.build_scripts import merge_eval_20260925 as merge_eval
from cursor_workspace.build_scripts import rebuild_eval_summary
from cursor_workspace.build_scripts import run_eval_20260925 as run_eval


def _record(content: str = "```python\ndef solve(data): return None\n```", *, raw=None, latency=1, error=None, status_code=200):
    return CompletionRecord(
        kind="test",
        endpoint="http://test/v1",
        model="test",
        request={},
        status_code=status_code,
        latency_ms=latency,
        prompt_tokens=None,
        completion_tokens=None,
        content=content,
        raw=raw or {"model": "test", "finish_reason": "stop"},
        usage=None,
        error=error,
    )


class _Client:
    def __init__(self, record):
        self.record = record

    def complete(self, *args, **kwargs):
        return self.record


def test_cp_is_in_run_eval_universe_and_duplicate_params_are_stable():
    items = run_eval.pick_items("hard", ["CP-09", "CP-09"])
    assert [item.id for item in items] == ["CP-09"]
    assert [(item.id, lang) for item, lang in run_eval.jobs_for(items, ["python", "python"])] == [("CP-09", "python")]


def test_run_one_records_salt_and_top_level_finish_reason(tmp_path: Path):
    item = run_eval.ALL_BY_ID["CP-09"]
    row = run_eval.run_one(
        _Client(_record(raw={"model": "stub", "finish_reason": "length"})),
        run_eval.Channel("stub", "stub", "http://test/v1", "KEY", 128, {}),
        item,
        "python",
        tmp_path,
        60,
    )
    assert row["status"] == "error"
    assert row["reason_code"] == "response_truncated"
    assert row["finish_reason"] == "length"
    assert row["salt"]
    assert row["prompt_sha256"] != row["base_prompt_sha256"]
    assert row["adapter_id"] == "coding"
    assert len(row["scorer_sha256"]) == 64


def test_run_eval_summary_accepts_fallback_rows_and_cp():
    rows = [{"channel": "stub", "item": "CP-09", "lang": "python", "status": "error", "passed": None, "score10": None}]
    summary = run_eval.summarize(rows, ["stub"])
    assert summary["stub"]["coding"]["errors"] == 1
    assert summary["stub"]["coding"]["judged"] == 0


def test_summary_never_combines_coding_and_reasoning_columns():
    rows = [
        {"channel": "stub", "item": "CP-09", "lang": "python", "status": "pass", "passed": True, "points": 20, "score10": 10, "score_percent": 100},
        {"channel": "stub", "item": "NX-09", "lang": None, "status": "fail", "passed": False, "points": 0, "score10": 0, "score_percent": 0},
    ]
    summary = run_eval.summarize(rows, ["stub"])["stub"]
    assert "overall" not in summary
    assert "extreme" not in summary
    assert {"coding", "reasoning"} <= set(summary)
    assert summary["coding"]["points"] == 20
    assert summary["coding"]["points_total"] == 20
    assert summary["reasoning"]["points"] == 0
    assert summary["coding"]["mean_percent"] == 100.0
    assert summary["reasoning"]["mean_percent"] == 0.0


def test_rebuild_summary_emits_column_totals_and_pass_at_k(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "meta.json").write_text(json.dumps({
        "models": ["stub"], "samples": 1, "pass_k": 1, "bank_version": "20261008",
        "experiment_id": "run", "langs": ["python"], "phase": "hard",
    }), encoding="utf-8")
    rows = [
        {"channel": "stub", "item": "CP-09", "lang": "python", "sample": 0, "status": "pass", "passed": True,
         "points": 20, "points_total": 20, "score10": 10, "score_percent": 100},
        {"channel": "stub", "item": "E-01", "lang": None, "sample": 0, "status": "fail", "passed": False,
         "points": 8, "points_total": 20, "positive_points": 14, "negative_points": 6, "net_points": 8,
         "score_percent": 40, "bank_id": "business-engineering"},
    ]
    (run_dir / "results.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["rebuild", str(run_dir)])
    assert rebuild_eval_summary.main() == 0
    payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    columns = payload["summary"]["stub"]
    assert "overall" not in columns
    assert columns["coding"]["points_total"] == 20
    assert columns["engineering"]["net_points"] == 8
    assert columns["engineering"]["pass_at_1"] == 0.0
    report = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "## 三栏汇总" in report
    assert "## 分组累计" in report
    assert "| coding |" in report
    assert "| engineering |" in report
    assert "overall" not in report


def test_timeout_is_zero_scored_and_enters_denominator():
    rows = [{"channel": "stub", "item": "NX-09", "lang": None, "sample": 0,
             "status": "fail", "reason_code": "timeout", "passed": False,
             "points": 0, "score10": 0.0, "score_percent": 0.0}]
    reasoning = run_eval.summarize(rows, ["stub"])["stub"]["reasoning"]
    assert reasoning["judged"] == 1
    assert reasoning["passed"] == 0
    assert reasoning["pass_at_1"] == 0.0
    assert reasoning["mean_percent"] == 0.0
    assert reasoning["errors"] == 0


def test_timeout_partial_content_keeps_points(tmp_path: Path):
    item = run_eval.ALL_BY_ID["NX-09"]
    text = '{"waiting":[],"last_end":18}'
    row = run_eval.run_one(
        _Client(_record(content=text, error="ReadTimeout")),
        run_eval.Channel("stub", "stub", "http://test/v1", "KEY", 128, {}),
        item, None, tmp_path, 60,
    )
    assert row["status"] == "fail"
    assert row["reason_code"] == "timeout_partial"
    assert row["points"] == 6
    assert row["score10"] == 3.0


def test_timeout_is_included_in_pass_at_k_samples():
    rows = [
        {"item": "NX-09", "lang": None, "sample": 0, "status": "fail", "passed": False, "score10": 0},
        {"item": "NX-09", "lang": None, "sample": 1, "status": "pass", "passed": True, "score10": 10},
        {"item": "NX-09", "lang": None, "sample": 2, "status": "fail", "passed": False, "score10": 0},
    ]
    assert run_eval._pass_at_k(rows, 2)[0] == 0.6667


def test_pass_at_k_uses_independent_samples_not_retry_rows():
    rows = [
        {"channel": "stub", "item": "NX-09", "lang": None, "sample": 0, "status": "fail", "passed": False, "score10": 0},
        {"channel": "stub", "item": "NX-09", "lang": None, "sample": 1, "status": "pass", "passed": True, "score10": 10},
        {"channel": "stub", "item": "NX-09", "lang": None, "sample": 2, "status": "fail", "passed": False, "score10": 0},
    ]
    summary = run_eval.summarize(rows, ["stub"], pass_k=2)
    reasoning = summary["stub"]["reasoning"]
    assert reasoning["pass_at_1"] == 0.3333
    assert reasoning["pass_at_k"] == 0.6667  # 1 - C(2,2) / C(3,2)
    assert reasoning["pass_at_k_eligible"] == 1

    assert run_eval.summarize(
        rows[:2], ["stub"], pass_k=3
    )["stub"]["reasoning"]["pass_at_k"] is None


def test_pass_at_k_requires_strict_boolean_pass_values():
    rows = [
        {"channel": "stub", "item": "NX-09", "lang": None, "sample": 0, "status": "pass", "passed": True, "score10": 10},
        {"channel": "stub", "item": "NX-09", "lang": None, "sample": 1, "status": "pass", "passed": 1, "score10": 10},
        {"channel": "stub", "item": "NX-09", "lang": None, "sample": 2, "status": "pass", "passed": "yes", "score10": 10},
    ]
    assert run_eval.summarize(rows, ["stub"], pass_k=2)["stub"]["reasoning"]["passed"] == 1
    assert run_eval.summarize(rows, ["stub"], pass_k=2)["stub"]["reasoning"]["pass_at_k"] == 0.6667
    assert merge_eval.pass_at_k(rows, 2) == 0.6667


def test_merge_keeps_success_when_retry_only_has_error(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "results.jsonl").write_text(json.dumps({"channel": "stub", "item": "CP-01", "lang": "python", "status": "pass", "passed": True, "score10": 10}) + "\n", encoding="utf-8")
    (second / "results.jsonl").write_text(json.dumps({"channel": "stub", "item": "CP-01", "lang": "python", "status": "error", "passed": None, "score10": None}) + "\n", encoding="utf-8")
    rows = merge_eval.load([first, second])
    assert rows[("stub", "CP-01", "python")]["status"] == "pass"


def test_merge_normalizes_legacy_timeout_into_zero_scored_failure(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "results.jsonl").write_text(
        json.dumps({"channel": "stub", "item": "NX-09", "status": "error",
                    "reason_code": "timeout", "passed": None, "points": None,
                    "score10": None}) + "\n", encoding="utf-8"
    )
    row = next(iter(merge_eval.load([run]).values()))
    assert row["status"] == "fail"
    assert row["passed"] is False
    assert row["points"] == 0
    assert row["score10"] == 0.0
    assert merge_eval.pass_at_k([row], 1) == 0.0


def test_merge_preserves_independent_sample_dimension_and_pass_at_k(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    base = {"channel": "stub", "item": "CP-01", "lang": "python", "status": "fail", "passed": False, "score10": 0}
    (first / "results.jsonl").write_text(
        json.dumps({**base, "sample": 0}) + "\n", encoding="utf-8"
    )
    (second / "results.jsonl").write_text(
        json.dumps({**base, "sample": 1, "status": "pass", "passed": True, "score10": 10}) + "\n", encoding="utf-8"
    )
    rows = merge_eval.load([first, second])
    assert len(rows) == 2
    assert merge_eval.pass_at_k(list(rows.values()), 2) == 1.0


def test_merge_distinguishes_sample_zero_across_runs(tmp_path: Path):
    dirs = [tmp_path / "run-a", tmp_path / "run-b"]
    for path in dirs:
        path.mkdir()
    base = {"channel": "stub", "item": "CP-01", "lang": "python", "sample": 0, "status": "pass", "passed": True, "score10": 10}
    for path, run_id in zip(dirs, ("run-a", "run-b")):
        (path / "results.jsonl").write_text(
            json.dumps({**base, "run_id": run_id}) + "\n", encoding="utf-8"
        )
    assert len(merge_eval.load(dirs)) == 2


