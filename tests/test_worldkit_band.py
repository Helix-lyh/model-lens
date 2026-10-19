"""4–8 分门禁：启发式自洽答卷落在区间内；主值不能被大量错方案共享。"""
import json
from pathlib import Path

from eval_bank_20260925.worldkit import answers, band, core, render
from eval_bank_20260925.worldkit.families import family_of, line, signal, trip, ward

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
    assert 4 <= got["heuristics"][0]["points"] <= 8


def test_trip_all_bike_and_local_greedy_both_checked():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes20/trip.json").read_text())
    got = band.accept(trip.FAMILY, world)
    assert got is not None
    assert len(got["heuristics"]) >= 1
    assert all(4 <= h["points"] <= 8 for h in got["heuristics"])


def test_scenes_band_worlds_exist():
    names = (
        "delivery", "trip", "elevator", "line", "signal",
        "kitchen", "ward", "charge", "push", "yard",
    )
    root = ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band"
    man = json.loads((root / "manifest.json").read_text())
    assert [it["file"].removesuffix(".json") for it in man["items"]] == list(names)
    assert man["sum_points"] == 43
    assert "推出" in man["goal"] and "超时" in man["goal"]
    for name in names:
        assert (root / f"{name}.json").exists()


def test_scenes_band_reference_full_and_no_leaks():
    root = ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band"
    man = json.loads((root / "manifest.json").read_text())
    for it in man["items"]:
        world = json.loads((root / it["file"]).read_text(encoding="utf-8"))
        fam = family_of(world)
        assert world["family"] == it["family"]
        assert render.leaks(render.render_prompt(fam, world)) == []
        if it["family"] == "delivery":
            continue
        sol = core.solve(fam, world, core.Budget(80_000, 90))
        assert sol.status == "ok"
        key = core.answers(fam, world)
        ref = answers.reference_text(world, key, core.Solver(fam), best=sol.best)
        assert answers.score(fam, world, key, ref, best=sol.best)["passed"]


def test_patched_signal_offset_shift_keeps_greedy_in_band():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band/signal.json").read_text())
    assert world["questions"][-1]["cf"] == "offset_shift"
    prompt = render.render_prompt(signal.FAMILY, world)
    assert "中绿灯 22 秒" in prompt
    assert "5 个相位" in prompt
    got = band.accept(signal.FAMILY, world)
    assert got is not None
    assert all(4 <= h["points"] <= 8 for h in got["heuristics"])
    assert got["cf"] != got["optimal"]["delay"]


def test_elevator_and_delivery_count_primary_matches():
    from eval_bank_20260925.worldkit.families import delivery, elevator
    ew = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band/elevator.json").read_text())
    es = core.solve(elevator.FAMILY, ew)
    assert es.n_primary >= 1
    assert es.n_shared >= 1
    dw = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band/delivery.json").read_text())
    ds = core.solve(delivery.FAMILY, dw, core.Budget(80_000, 90))
    assert ds.n_primary >= 1
    assert ds.n_shared >= 1


def test_ward_counterfactual_shifts_doctor_not_deletes_mix():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band/ward.json").read_text())
    assert world["questions"][-1]["cf"] == "doctor_early"
    assert "mix" in world["modules"]
    cf = ward.FAMILY.counterfactuals["doctor_early"].transform(world)
    assert cf["modules"]["doctor"]["at"] == world["modules"]["doctor"]["early"]
    assert "mix" in cf["modules"]


def test_scenes_band_charge_keeps_original_point_split():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band/charge.json").read_text())
    pts = {q["name"]: q["points"] for q in world["questions"]}
    assert pts == {"plan": 6, "late": 5, "late_n": 4, "cf_late": 5}


def test_solution_counts_how_many_plans_share_the_gold_primary():
    world = json.loads((ROOT / "eval_bank_20260925/worldkit/worlds/scenes20/line.json").read_text())
    sol = core.solve(line.FAMILY, world)
    assert sol.n_feasible > 0
    assert 1 <= sol.n_primary <= sol.n_feasible
    assert 1 <= sol.n_shared <= sol.n_feasible
