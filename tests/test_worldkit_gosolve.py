"""Go 求解与 Python 门禁对拍。极难档只对 1 个世界，并检查耗时。"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import pytest

from eval_bank_20260925.worldkit import accel, gates, sample
from eval_bank_20260925.worldkit.families import delivery

ROOT = Path(__file__).resolve().parents[1]
FAM = delivery.FAMILY


def _go(world: dict, seconds: float = 60) -> dict:
    return accel.run_gates(world, fail_fast=False, max_plans=200_000, seconds=seconds)


def _same(go: dict, py: dict) -> None:
    assert go["accept"] == py["accept"], (go["reasons"], py["reasons"], go["answer"], py["answer"])
    assert go["answer"] == py["answer"]
    assert go.get("boundary") == py.get("boundary")
    assert go.get("readings") == py.get("readings")
    if "deletion" in py:
        g = {d["condition"]: set(d["changed"]) for d in go["deletion"]}
        p = {d["condition"]: set(d["changed"]) for d in py["deletion"]}
        assert g == p
        assert go["degree"]["degree"] == py["degree"]["degree"]
        assert go["degree"]["ok"] == py["degree"]["ok"]
    if "conflict" in py:
        assert set(go["conflict"]["core"]) == set(py["conflict"]["core"])
        assert go["conflict"]["ok"] == py["conflict"]["ok"]
    assert (go.get("oracle") or {}).get("ok") == (py.get("oracle") or {}).get("ok")


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_presets_match_python(item_id):
    world = json.loads((ROOT / f"eval_bank_20260925/worldkit/worlds/delivery/presets/{item_id}.json").read_text())
    _same(_go(world), gates.run_gates(FAM, world))


@pytest.mark.parametrize("tier,seed", [("简单", 3), ("简单", 11)])
def test_sampled_worlds_match_python(tier, seed):
    cfg = sample.load_config("delivery")
    world = delivery.sample(random.Random(seed), cfg, cfg["tiers"][tier])
    _same(_go(world), gates.run_gates(FAM, world))


def test_large_tier_answer_matches_python_solve():
    """7 单加随时回站有 32 万条路线，只对拍一次求解的答案，不对拍整套 Python 门禁。"""
    from eval_bank_20260925.worldkit import core
    cfg = sample.load_config("delivery")
    world = delivery.sample(random.Random(7), cfg, cfg["tiers"]["困难"])
    t = time.time()
    go = accel.run_gates(world, fail_fast=False, max_plans=400_000, seconds=120)
    elapsed = time.time() - t
    solver = core.Solver(FAM, core.Budget(400_000, 120))
    assert go["answer"] == core.answers(FAM, world, solver)
    assert elapsed < 45, elapsed
