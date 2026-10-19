"""results.jsonl 原子写入、去重与续跑。"""
from __future__ import annotations

import json
from pathlib import Path

from cursor_workspace.build_scripts import run_eval_20260925 as run_eval


def _row(item, status="fail", reason="content_mismatch", sample=0, channel="a"):
    return {"channel": channel, "item": item, "lang": None, "sample": sample, "status": status,
            "reason_code": reason, "passed": False if status == "fail" else None,
            "points": 0 if status == "fail" else None, "points_total": 20,
            "score10": 0.0 if status == "fail" else None, "bank_id": "business-reasoning"}


def test_write_summary_keeps_rows_already_on_disk(tmp_path: Path):
    disk = [_row("NX-09"), _row("NX-10")]
    (tmp_path / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in disk) + '{"half', encoding="utf-8")
    final = run_eval.write_summary(tmp_path, {}, [_row("NX-11")], {"models": ["a"]})
    items = sorted(r["item"] for r in final)
    assert items == ["NX-09", "NX-10", "NX-11"]
    on_disk = run_eval.read_results(tmp_path / "results.jsonl")
    assert sorted(r["item"] for r in on_disk) == items
    assert not list(tmp_path.glob(".*.tmp"))
    assert (tmp_path / "summary.md").is_file()


def test_dedupe_keeps_result_over_later_request_error():
    rows = [_row("NX-09"), _row("NX-09", status="error", reason="request_error"), _row("NX-10", status="error", reason="request_error"),
            _row("NX-10", status="fail", reason="content_mismatch")]
    kept = {r["item"]: r for r in run_eval.dedupe_rows(rows)}
    assert kept["NX-09"]["status"] == "fail"
    assert kept["NX-10"]["status"] == "fail"


def test_resume_skips_recorded_results_but_reruns_request_errors():
    rows = [_row("NX-09"), _row("NX-10", status="error", reason="request_error"),
            _row("NX-11", status="error", reason="response_truncated")]
    skip = run_eval.resume_skip(rows)
    assert ("a", "NX-09", None, 0) in skip
    assert ("a", "NX-11", None, 0) in skip
    assert ("a", "NX-10", None, 0) not in skip


def test_run_channel_honours_skip(tmp_path: Path, monkeypatch):
    calls = []

    def fake_run_one(client, ch, item, lang, out_dir, timeout_s, sample=0, cancel=None):
        calls.append(item.id)
        return _row(item.id, channel=ch.name)

    monkeypatch.setattr(run_eval, "run_one", fake_run_one)
    monkeypatch.setattr(run_eval, "ChatClient", lambda *a, **k: object())
    monkeypatch.setenv("KEY", "x")
    items = run_eval.pick_items("hard", ["NX-09", "NX-10"])
    ch = run_eval.Channel("a", "a", "http://test/v1", "KEY", 128, {})
    rows = run_eval.run_channel(ch, run_eval.jobs_for(items, ["python"]), tmp_path, 2,
                                skip={("a", "NX-09", None, 0)})
    assert calls == ["NX-10"]
    assert [r["item"] for r in rows] == ["NX-10"]
