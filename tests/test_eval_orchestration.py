from __future__ import annotations

import json
from pathlib import Path

from src.types import CompletionRecord

from cursor_workspace.build_scripts import merge_eval_20260925 as merge_eval
from cursor_workspace.build_scripts import run_eval_20260925 as run_eval
import eval_bank_20260925.challenge_live as challenge_live


def _record(content: str = "```python\ndef solve(data): return None\n```", *, raw=None, latency=1):
    return CompletionRecord(
        kind="test",
        endpoint="http://test/v1",
        model="test",
        request={},
        status_code=200,
        latency_ms=latency,
        prompt_tokens=None,
        completion_tokens=None,
        content=content,
        raw=raw or {"model": "test", "finish_reason": "stop"},
        usage=None,
    )


class _Client:
    def __init__(self, record):
        self.record = record

    def complete(self, *args, **kwargs):
        return self.record


def test_cp_is_in_run_eval_universe_and_duplicate_params_are_stable():
    items = run_eval.pick_items("quick", ["CP-01", "CP-01"])
    assert [item.id for item in items] == ["CP-01"]
    assert [(item.id, lang) for item, lang in run_eval.jobs_for(items, ["python", "python"])] == [("CP-01", "python")]


def test_run_one_records_salt_and_top_level_finish_reason(tmp_path: Path):
    item = run_eval.CP_BY_ID["CP-01"]
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


def test_run_eval_summary_accepts_fallback_rows_and_cp():
    rows = [{"channel": "stub", "item": "CP-01", "lang": "python", "status": "error", "passed": None, "score10": None}]
    summary = run_eval.summarize(rows, ["stub"])
    assert summary["stub"]["coding"]["errors"] == 1
    assert summary["stub"]["coding"]["judged"] == 0


def test_pass_at_k_uses_independent_samples_not_retry_rows():
    rows = [
        {"channel": "stub", "item": "R-E-01", "lang": None, "sample": 0, "status": "fail", "passed": False, "score10": 0},
        {"channel": "stub", "item": "R-E-01", "lang": None, "sample": 1, "status": "pass", "passed": True, "score10": 10},
        {"channel": "stub", "item": "R-E-01", "lang": None, "sample": 2, "status": "fail", "passed": False, "score10": 0},
    ]
    summary = run_eval.summarize(rows, ["stub"], pass_k=2)
    overall = summary["stub"]["overall"]
    assert overall["pass_at_1"] == 0.3333
    assert overall["pass_at_k"] == 0.6667  # 1 - C(2,2) / C(3,2)
    assert overall["pass_at_k_eligible"] == 1

    assert run_eval.summarize(
        rows[:2], ["stub"], pass_k=3
    )["stub"]["overall"]["pass_at_k"] is None


def test_pass_at_k_requires_strict_boolean_pass_values():
    rows = [
        {"channel": "stub", "item": "R-E-01", "lang": None, "sample": 0, "status": "pass", "passed": True, "score10": 10},
        {"channel": "stub", "item": "R-E-01", "lang": None, "sample": 1, "status": "pass", "passed": 1, "score10": 10},
        {"channel": "stub", "item": "R-E-01", "lang": None, "sample": 2, "status": "pass", "passed": "yes", "score10": 10},
    ]
    assert run_eval.summarize(rows, ["stub"], pass_k=2)["stub"]["overall"]["passed"] == 1
    assert run_eval.summarize(rows, ["stub"], pass_k=2)["stub"]["overall"]["pass_at_k"] == 0.6667
    assert merge_eval.pass_at_k(rows, 2) == 0.6667


def test_challenge_live_pass_at_k_requires_strict_boolean_pass_values():
    rows = [
        {"item": "CP-01", "status": "pass", "passed": True},
        {"item": "CP-01", "status": "pass", "passed": 1},
        {"item": "CP-01", "status": "pass", "passed": "yes"},
    ]
    result, eligible, _ = challenge_live.pass_at_k(rows, 2)
    assert result == 0.6667
    assert eligible == 1


def test_merge_keeps_success_when_retry_only_has_error(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "results.jsonl").write_text(json.dumps({"channel": "stub", "item": "CP-01", "lang": "python", "status": "pass", "passed": True, "score10": 10}) + "\n", encoding="utf-8")
    (second / "results.jsonl").write_text(json.dumps({"channel": "stub", "item": "CP-01", "lang": "python", "status": "error", "passed": None, "score10": None}) + "\n", encoding="utf-8")
    rows = merge_eval.load([first, second])
    assert rows[("stub", "CP-01", "python")]["status"] == "pass"


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


def test_challenge_live_scores_coding_and_rejects_truncation(tmp_path: Path, monkeypatch):
    item = challenge_live.coding_items()[0]

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def complete(self, *args, **kwargs):
            return _record(raw={"model": "stub", "finish_reason": "length"})

    monkeypatch.setattr(challenge_live, "ChatClient", Client)
    monkeypatch.setattr(challenge_live, "score_saved", lambda *args, **kwargs: {"status": "pass", "reason_code": "ok", "passed": True, "points": 20, "score10": 10})
    row = challenge_live.run_one(item, tmp_path, {"base_url": "http://x/v1", "api_key_env": "KEY", "model": "stub", "timeout_s": 60, "max_tokens": 32, "seed": 1})
    assert row["status"] == "error"
    assert row["reason_code"] == "response_truncated"
    assert row["finish_reason"] == "length"
