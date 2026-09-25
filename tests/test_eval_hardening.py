from __future__ import annotations

from eval_bank_20260925.runner import score_coding
from eval_bank_20260925.challenge_coding import score_saved
from eval_bank_20260925.score import score_reasoning
from src.grade import _forbidden_import


def test_candidate_cannot_forge_fixture_points() -> None:
    payload = """```python
import atexit
atexit.register(lambda: print("POINTS 20/20"))
def solve(data):
    return None
```"""
    result = score_coding("P-E-01", payload, "python")
    assert result.status == "fail"
    assert result.points == 0.0
    assert result.score10 == 0.0


def test_abnormal_exit_cannot_supply_partial_points() -> None:
    payload = """```python
import os
def solve(data):
    os._exit(0)
```"""
    result = score_coding("P-E-01", payload, "python")
    assert result.status == "fail"
    assert result.points == 0.0
    assert result.score10 == 0.0


def test_cp_saved_uses_same_fail_closed_score_contract() -> None:
    payload = """```python
import atexit
atexit.register(lambda: print("POINTS 20/20"))
def solve(data):
    return None
```"""
    result = score_saved("CP-01", payload)
    assert result["status"] == "fail"
    assert result["points"] == 0.0
    assert result["score10"] == 0.0


def test_forbidden_loader_comment_and_eval_bypasses_are_rejected() -> None:
    assert _forbidden_import('import ( /* hide */ "net" )', "go") == "net"
    assert _forbidden_import('const x = eval("require")("child_process")', "typescript")


def test_reasoning_parser_accepts_bom_and_non_text_is_format_error() -> None:
    bom = '\ufeff{"likelihood_u":[1,1],"likelihood_v":[1,2],"posterior_u":[1,2],"both_red":[1,4]}'
    assert score_reasoning("R-E-02", bom).passed is True
    assert score_reasoning("R-E-02", None).reason_code == "format_error"
