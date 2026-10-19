"""2–6 分门禁：启发式自洽答卷落在区间内；主值不能被大量错方案共享。"""
import json
from pathlib import Path

from eval_bank_20260925.worldkit import answers, band, core
from eval_bank_20260925.worldkit.families import line, signal, trip

ROOT = Path(__file__).resolve().parents[1]


def test_replay_text_uses_the_plan_own_integers():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes20/line.json").read_text())
    fam = line.FAMILY
    plan = fam.greedies(world)[0]
    out = fam.simulate(world, plan)
    text = answers.replay_text(world, plan, out.metrics, out.metrics)
    assert text.startswith("ANSWER: ")
    assert str(out.metrics["tardiness"]) in text


def test_line_keeper_heuristics_sit_in_band():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes20/line.json").read_text())
    got = band.accept(line.FAMILY, world, bite=None)
    assert got is not None
    assert 2 <= got["heuristics"][0]["points"] <= 6


def test_trip_all_bike_and_local_greedy_both_checked():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes20/trip.json").read_text())
    got = band.accept(trip.FAMILY, world)
    assert got is not None
    assert len(got["heuristics"]) >= 1
    assert all(2 <= h["points"] <= 6 for h in got["heuristics"])


def test_scenes_band_worlds_exist():
    names = (
        "delivery", "trip", "elevator", "line", "signal",
        "kitchen", "ward", "charge", "push", "yard",
    )
    root = ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band"
    man = json.loads((root / "manifest.json").read_text())
    assert [it["file"].removesuffix(".json") for it in man["items"]] == list(names)
    for name in names:
        assert (root / f"{name}.json").exists()


def test_patched_signal_offset_shift_keeps_greedy_in_band():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band/signal.json").read_text())
    assert world["questions"][-1]["cf"] == "offset_shift"
    got = band.accept(signal.FAMILY, world)
    assert got is not None
    assert all(2 <= h["points"] <= 6 for h in got["heuristics"])
    assert got["cf"] != got["optimal"]["delay"]


def test_solution_counts_how_many_plans_share_the_gold_primary():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes20/line.json").read_text())
    sol = core.solve(line.FAMILY, world)
    assert sol.n_feasible > 0
    assert 1 <= sol.n_primary <= sol.n_feasible
    assert 1 <= sol.n_shared <= sol.n_feasible
