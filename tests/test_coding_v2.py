"""Adversarial v2 checks for the twelve coding contracts.

These tests exercise the real fixtures through the sandbox and use independent
oracles.  They intentionally avoid trusting a solution's POINTS marker.
"""
from pathlib import Path
import re

from src.bank import repo_root
from src.grade import run_python_sandbox

ROOT = repo_root()
PY = ROOT / "bank/tests"

def _has_points_marker(text: str) -> bool:
    # Existing fixtures use both literal and f-string markers.
    return bool(re.search(r"POINTS\s+[^\n]*?/\s*\d+", text))

def test_all_coding_fixtures_have_marker_and_solution_contract():
    fixtures = [*PY.glob("b*.py"), *(PY / "go").glob("*_test.go"), *(PY / "ts").glob("*.ts")]
    assert fixtures
    for p in fixtures:
        text = p.read_text(encoding="utf-8")
        assert _has_points_marker(text), p
        assert "solution" in text, p

def test_python_hard_extreme_fixtures_reject_constant_examples():
    mutants = {
        "b04_pack_runs.py": "def pack_runs(xs): return []\n",
        "b09_tag_scores.py": "def tag_scores(items): return {}\n",
        "b10_render.py": "def render(template, vars): return template\n",
        "b11_limiter.py": "class SlidingLimiter:\n def __init__(self, limit, window): pass\n def allow(self, ts): return True\n",
        "b12_plan_tasks.py": "def plan_tasks(tasks, deps): return sorted(tasks)\n",
        "b13_replay_counter.py": "def replay_counter(log): return {'balance':0,'accepted':[],'rejected':[]}\n",
        "b14_merge_budget.py": "def merge_budget(intervals, budget): return {'ok':True,'intervals':intervals,'reason':'empty'}\n",
        "b15_knapsack.py": "def bounded_knapsack(items, capacity): return {'value':0,'weight':0,'indices':[]}\n",
        "b16_mvcc.py": "def apply_transactions(initial, txns): return {'state':initial,'statuses':{}}\n",
        "b17_order_events.py": "def order_events(events): return {'state':'CREATED','applied':[],'rejected':[]}\n",
    }
    for name, code in mutants.items():
        status, detail = run_python_sandbox(code, PY / name)
        assert status == "fail", (name, detail)

def test_python_fixture_sources_have_multiple_cases():
    for name in ("b04_pack_runs.py", "b09_tag_scores.py", "b10_render.py", "b11_limiter.py", "b12_plan_tasks.py", "b13_replay_counter.py", "b14_merge_budget.py", "b15_knapsack.py", "b16_mvcc.py", "b17_order_events.py"):
        p = PY / name
        text = p.read_text(encoding="utf-8")
        cases = len(re.findall(r"(?:n\s*\+=|\b(?:_hit|hit|_check)\s*\()", text))
        assert cases >= 2, (p, cases)
