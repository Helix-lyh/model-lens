"""成绩页：固定分母、截断显示、按 --run/--channel 生成、不在 import 时执行。"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from cursor_workspace.build_scripts import run_eval_20260925 as run_eval

ITEMS = [f"CP-{n:02d}" for n in range(9, 19)] + [f"E-{n:02d}" for n in range(1, 11)] + [f"NX-{n:02d}" for n in range(9, 19)]


def _rows(channel: str, truncated: set[str]) -> list[dict]:
    rows = []
    for item in ITEMS:
        bank = {"CP": "business-coding", "E": "business-engineering", "NX": "business-reasoning"}[item.split("-")[0]]
        base = {"channel": channel, "model": channel, "item": item, "lang": "python" if item.startswith("CP") else None,
                "sample": 0, "bank_id": bank, "bank_version": "v", "scorer_sha256": "s" * 64,
                "base_prompt_sha256": "p" * 64, "points_total": 20}
        if item in truncated:
            base.update(status="error", reason_code="response_truncated", passed=None, points=None,
                        score10=None, truncated=True, finish_reason="length")
        elif item.startswith("E-"):
            base.update(status="fail", reason_code="content_mismatch", passed=False, points=10,
                        positive_points=10, negative_points=0, net_points=10, score10=None, score_percent=50.0)
        else:
            base.update(status="fail", reason_code="tests_failed", passed=False, points=10, score10=5.0,
                        score_percent=50.0, groups=[])
        rows.append(base)
    return rows


def _run_dir(tmp_path: Path) -> Path:
    run = tmp_path / "eval-x-hard"
    run.mkdir()
    rows = _rows("a", set()) + _rows("b", {"NX-09", "E-01"})
    (run / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (run / "meta.json").write_text(json.dumps({"models": ["a", "b"], "items": ITEMS, "bank_version": "v",
                                               "started_at": "20261009T000935"}), encoding="utf-8")
    return run


def test_ledger_module_import_has_no_side_effects():
    module = importlib.import_module("cursor_workspace.build_scripts.build_eval_ledger_20261006")
    assert hasattr(module, "build_html")
    assert not hasattr(module, "HTML")


def test_ledger_accepts_run_channel_and_truncation(tmp_path: Path):
    from cursor_workspace.build_scripts import build_eval_ledger_20261006 as ledger
    run = _run_dir(tmp_path)
    out = tmp_path / "ledger.html"
    assert ledger.main(["--run", str(run), "--channel", "b", "--out", str(out)]) == 0
    html = out.read_text(encoding="utf-8")
    assert html.count("截断（0分）") == 2
    _, scores = ledger.build_html(run, "b")
    assert scores == {"coding": "50.0", "engineering": "45.0", "reasoning": "45.0"}


def test_matrix_uses_fixed_denominator_and_labels_truncation(tmp_path: Path):
    from cursor_workspace.build_scripts import build_eval_matrix as matrix
    run = _run_dir(tmp_path)
    out = tmp_path / "m.html"
    import sys
    argv, sys.argv = sys.argv, ["x", "--run", str(run), "--out", str(out)]
    try:
        assert matrix.main() == 0
    finally:
        sys.argv = argv
    html = out.read_text(encoding="utf-8")
    assert "截断（0分）" in html
    assert "原始分 90 / 200 分" in html  # 推理：9 题×10 分，截断 1 题记 0，分母仍是 200
    assert "已判口径" in html


def test_publish_reports_passes_run_dir(tmp_path: Path):
    commands = run_eval.report_commands(tmp_path, ["a", "b"])
    flat = [" ".join(command) for command, _label in commands]
    assert len(commands) == 3
    assert all(f"--run {tmp_path}" in line for line in flat)
    assert any("--channel b" in line for line in flat)
    assert all(str(tmp_path) in line.split("--out", 1)[1] for line in flat)
