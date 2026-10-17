"""20261022 推理题：并列择支推广（NX-10/12/14/15/18）、NX-16 语义修正、NX-17 度数≥3。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skip(reason="superseded by test_next_reasoning_20261023")

from eval_bank_20260925 import reasoning_gen as gen
from eval_bank_20260925.next_reasoning import FROZEN, ITEMS, reference_text, render_reasoning_prompt, score_reasoning

ROOT = Path(__file__).resolve().parents[1]
ROWS = {row["item_id"]: row for row in FROZEN["items"]}
INST = {k: v["instance"] for k, v in ROWS.items()}
AUDITED = ("NX-10", "NX-12", "NX-14", "NX-15", "NX-16", "NX-17", "NX-18")


def test_bank_version_20261022():
    assert FROZEN["version"] == gen.VERSION == "20261022"


@pytest.mark.parametrize("item_id", sorted(ROWS))
def test_main_deletion_changes_main_keys(item_id):
    for row in ROWS[item_id]["deletion"]:
        assert row["ok"], (item_id, row)
        assert row["changed"], (item_id, row)
        assert all(not c.startswith("cf_") for c in row["changed"])


@pytest.mark.parametrize("item_id", AUDITED)
def test_audited_mesh_degree(item_id):
    deg = ROWS[item_id]["degree"]
    assert deg["degree"]
    assert deg["ok"]
    assert min(deg["degree"].values()) >= 3
    assert len(deg["degree"]) >= 4


@pytest.mark.parametrize("item_id", ("NX-10", "NX-13", "NX-15"))
def test_degree_ge3_for_patched(item_id):
    deg = ROWS[item_id]["degree"]
    assert deg["ok"] and min(deg["degree"].values()) >= 3


@pytest.mark.parametrize("item_id", AUDITED)
def test_degree_report_matches_frozen(item_id):
    assert gen.degree_report(item_id, INST[item_id])["degree"] == ROWS[item_id]["degree"]["degree"]


def test_nx10_tie_branch_not_pure_sim():
    ss = ROWS["NX-10"].get("search_space") or {}
    assert ss.get("scored", 0) >= 2
    assert ROWS["NX-10"]["answer"]["total_cost"] == 61
    assert INST["NX-10"]["aging_cap"] >= 2
    live = gen._apply_mutex_nx10(INST["NX-10"])
    from eval_bank_20260925 import reasoning_mesh_20261022 as mesh
    opt = mesh.solve_nx10_core(live, "opt")
    lex = mesh.solve_nx10_core(live, "lex")
    assert (opt["total_cost"], opt["rejected"]) != (lex["total_cost"], lex["rejected"])


def test_nx16_cross_day_harder():
    assert INST["NX-16"]["shelf"] >= 3
    assert INST["NX-16"]["bulk_window"] >= 2
    assert len(INST["NX-16"]["days"]) >= 10
    assert ROWS["NX-16"]["answer"]["waste_sum"] >= 1
    assert ROWS["NX-16"]["answer"] == {"profit": 693, "waste_sum": 1}


def test_nx16_window_counts_purchase_days_only():
    """「近 2 个进货日」只统计进货量>0 的天：对照「近 2 天」读法（旧求解器 651）。"""
    from eval_bank_20260925 import reasoning_mesh_20261022 as mesh
    plan, count = mesh.plan_nx16(INST["NX-16"])
    assert count == 1 and plan["profit"] == 693


@pytest.mark.parametrize("item_id", ("NX-12", "NX-18"))
def test_delivery_tie_branch_bears_weight(item_id):
    from eval_bank_20260925 import reasoning_mesh_20261022 as mesh
    live = gen._apply_mutex_delivery(INST[item_id])
    rows = mesh._rank3(live)
    top = [r for r in rows if r[0] == rows[0][0]]
    assert len({r[5] for r in top}) >= 2
    assert min(top, key=lambda r: r[1])[5] != rows[0][5]
    assert ROWS[item_id]["answer"]["walk"] == rows[0][5]


def test_nx15_tie_branch_bears_weight():
    from eval_bank_20260925 import reasoning_mesh_20261022 as mesh
    live = gen._apply_mutex_nx15(INST["NX-15"])
    opt = mesh.solve_nx15_tie(live, "opt")
    lex = mesh.solve_nx15_tie(live, "lex")
    assert opt["emergency_wait"] < lex["emergency_wait"]
    assert ROWS["NX-15"]["answer"]["emergency_wait"] == opt["emergency_wait"]


def test_nx14_preserved():
    assert ROWS["NX-14"]["answer"]["total_cost"] == 26


def test_reference_scores_full():
    for item in ITEMS:
        full = score_reasoning(item.item_id, reference_text(item.item_id))
        assert full["passed"] and full["points"] == 20


PROCEDURE_LEAKS = [
    "逐步模拟", "一步一步", "step by step", "按如下步骤", "解题思路",
    "注意陷阱", "本题陷阱", "难点提示", "参考答案", "正确答案是",
]


@pytest.mark.parametrize("item", ITEMS, ids=lambda it: it.item_id)
def test_prompt_open_no_schema_leak(item):
    text = render_reasoning_prompt(item.item_id)
    for phrase in PROCEDURE_LEAKS:
        assert phrase not in text
    for banned in ("JSON", "Schema", "只含以下字段", "active_shock", "cf_", "flood", "closed-", "id 为"):
        assert banned not in text, (item.item_id, banned)
    assert "ANSWER:" in text and text.rstrip().endswith("用英文逗号分隔。")


def test_generator_check_script():
    script = ROOT / "cursor_workspace" / "build_scripts" / "gen_reasoning_20261022.py"
    out = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr
