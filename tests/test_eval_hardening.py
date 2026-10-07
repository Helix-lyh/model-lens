"""Sandbox fail-closed checks on the live coding and reasoning scorers."""

from __future__ import annotations

import json

from eval_bank_20260925.next_coding import score_saved
from eval_bank_20260925.next_reasoning import reference_answer, score_reasoning
from src.grade import _forbidden_import


def test_candidate_cannot_forge_fixture_points() -> None:
    payload = """```python
import atexit
atexit.register(lambda: print("POINTS 20/20"))
def describe():
    return {"keys": {}, "actions": {}, "states": {}, "trace": {"dup": "DUP"}}
def solve(data):
    return None
```"""
    result = score_saved("CP-09", payload)
    assert result["status"] == "fail"
    assert result["points"] == 0.0
    assert result["score10"] == 0.0


def test_abnormal_exit_cannot_supply_partial_points() -> None:
    payload = """```python
import os
def describe():
    return {"keys": {}, "actions": {}, "states": {}, "trace": {"dup": "DUP"}}
def solve(data):
    os._exit(0)
```"""
    result = score_saved("CP-09", payload)
    assert result["status"] == "fail"
    assert result["points"] == 0.0
    assert result["score10"] == 0.0


def test_forbidden_loader_comment_and_eval_bypasses_are_rejected() -> None:
    assert _forbidden_import('import ( /* hide */ "net" )', "go") == "net"
    assert _forbidden_import('const x = eval("require")("child_process")', "typescript")


def test_reasoning_parser_accepts_bom_and_non_text_is_format_error() -> None:
    text = "\ufeff" + json.dumps(reference_answer("NX-09"), ensure_ascii=False)
    assert score_reasoning("NX-09", text)["passed"] is True
    assert score_reasoning("NX-09", None)["reason_code"] == "format_error"
