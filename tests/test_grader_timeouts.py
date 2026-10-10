"""判分超时：使用题目设定；编译超时记判分环境错误；判分并发独立。"""
from __future__ import annotations

import subprocess
import threading
import time

import pytest

import src.grade as grade
from eval_bank_20260925.evaluation import unjudged_execution
from src.types import SampleGrade


def test_go_and_ts_receive_question_timeout(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(grade, "run_go_sandbox", lambda *a, **k: seen.setdefault("go", k) and ("fail", "x"))
    monkeypatch.setattr(grade, "run_ts_sandbox", lambda *a, **k: seen.setdefault("ts", k) and ("fail", "x"))
    grade._run_lang_sandbox("go", "", tmp_path / "t", timeout_s=60)
    grade._run_lang_sandbox("typescript", "", tmp_path / "t", timeout_s=60)
    assert seen["go"]["timeout_s"] == 60
    assert seen["ts"]["timeout_s"] == 60


def test_go_build_timeout_is_grader_error(monkeypatch, tmp_path):
    from src.toolchain import discover
    if discover().missing_for("go"):
        pytest.skip("go toolchain missing")
    real_run = subprocess.run

    def fake_run(argv, *args, **kwargs):
        if "-c" in argv:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(grade.subprocess, "run", fake_run)
    tests = tmp_path / "x_test.go"
    tests.write_text("package main\n", encoding="utf-8")
    status, detail = grade.run_go_sandbox("package main\n", tests, timeout_s=5)
    assert status == "error"
    assert detail.startswith("grader_timeout")
    verdict = unjudged_execution(SampleGrade(temperature=0.0, status=status, passed=None, detail=detail, content=""))
    assert verdict["reason_code"] == "grader_timeout"
    assert verdict["points"] is None


def test_grader_slots_limit_concurrent_sandboxes(monkeypatch):
    active, peak = 0, 0
    lock = threading.Lock()

    def slow(*args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1

    grade.set_grader_concurrency(1)
    try:
        def work():
            with grade.grader_slot():
                slow()
        threads = [threading.Thread(target=work) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        grade.set_grader_concurrency(4)
    assert peak == 1
