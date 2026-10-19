"""十个场景各一道极难题：手算轨迹，以及冻结题的贪心恰好 4 分。"""
import json
from pathlib import Path

from eval_bank_20260925.worldkit import answers, core, render
from eval_bank_20260925.worldkit.families import charge, deice, family_of, gate, kitchen, signal, ward

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "eval_bank_20260925/worldkit/worlds/scenes10"


def test_signal_one_vehicle_each_phase():
    world = {
        "family": "signal",
        "data": {
            "greens": {"S": 10, "L": 10},
            "lost": 0,
            "headway": 2,
            "miss": 100,
            "vehicles": [{"phase": p, "at": 0, "n": 1} for p in signal.PHASES],
        },
        "modules": {},
        "objective": ["delay", "max_delay"],
        "questions": signal.FAMILY.questions(),
        "background": [],
    }
    out = signal.FAMILY.simulate(world, ("NSS", "EWS", "NLS", "ELS"))
    assert out is not None
    assert out.metrics == {"delay": 60, "max_delay": 30, "wait_n": 3}


def test_deice_two_planes_no_second_spray():
    world = {
        "family": "deice",
        "data": {"planes": [
            {"id": "A", "ready": 0, "slot": 0, "deice": 5, "hold": 20},
            {"id": "B", "ready": 0, "slot": 0, "deice": 5, "hold": 20},
        ]},
        "modules": {},
        "objective": ["delay", "redeice"],
        "questions": deice.FAMILY.questions(),
        "background": [],
    }
    out = deice.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    assert out.metrics["delay"] == 15
    assert out.metrics["redeice"] == 0


def test_charge_half_rate_overlap():
    world = {
        "family": "charge",
        "data": {"cars": [
            {"id": "A", "need": 4, "depart": 3},
            {"id": "B", "need": 4, "depart": 3},
        ]},
        "modules": {"share": {}},
        "objective": ["late", "late_n"],
        "questions": charge.FAMILY.questions(),
        "background": [],
    }
    out = charge.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    # 两车 0 分钟同时插上，全程半格：4 个电量单位各要 8 分钟，迟到 5+5。
    assert out.metrics == {"late": 10, "late_n": 2}


def test_charge_block_idles_only_the_first_charger():
    world = {
        "family": "charge",
        "data": {"cars": [
            {"id": "A", "need": 4, "depart": 3},
            {"id": "B", "need": 4, "depart": 3},
        ]},
        "modules": {"share": {}, "block": {"lo": 0, "hi": 4}},
        "objective": ["late", "late_n"],
        "questions": charge.FAMILY.questions(),
        "background": [],
    }
    out = charge.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    # 甲桩前 4 分钟不供电，A 干等到 4 再满功率充满于 8；B 在乙桩单独满功率，4 分钟充满。
    assert out.metrics == {"late": 6, "late_n": 2}


def test_gate_bridge_first_exiles_a_large_widebody():
    world = gate.pinned_world()
    sol = core.solve(gate.FAMILY, world)
    assert sol.status == "ok"
    assert sol.best.metrics["pax_bus"] == 1000
    assert sol.best.metrics["remote_n"] == 3
    greedy = gate.greedy_bridge(world)
    gout = gate.FAMILY.simulate(world, greedy)
    assert gout.metrics["pax_bus"] == 2300
    assert gout.metrics["remote_n"] == 3
    cf = core.solve(gate.FAMILY, gate.FAMILY.counterfactuals["no_wide"].transform(world))
    assert cf.best.metrics["pax_bus"] == 900


def test_deice_flush_pushes_a_different_kind():
    world = {
        "family": "deice",
        "data": {"planes": [
            {"id": "A", "ready": 0, "slot": 0, "deice": 5, "hold": 20, "kind": "P"},
            {"id": "B", "ready": 0, "slot": 0, "deice": 5, "hold": 20, "kind": "Q"},
        ]},
        "modules": {"flush": {"minutes": 4}},
        "objective": ["delay", "redeice"],
        "questions": deice.FAMILY.questions(),
        "background": [],
    }
    out = deice.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    assert out.metrics["delay"] == 19
    assert out.metrics["redeice"] == 0


def test_kitchen_pan_sends_the_third_dish_to_the_later_burner():
    world = {
        "family": "kitchen",
        "data": {"dishes": [
            {"id": "A", "table": "T1", "cook": 6, "hold": 40, "pan": "炒"},
            {"id": "B", "table": "T1", "cook": 8, "hold": 40, "pan": "炖"},
            {"id": "C", "table": "T1", "cook": 4, "hold": 40, "pan": "炖"},
        ]},
        "modules": {"pan": {"minutes": 3}},
        "objective": ["makespan", "spoils"],
        "questions": kitchen.FAMILY.questions(),
        "background": [],
    }
    out = kitchen.FAMILY.simulate(world, ("A", "B", "C"))
    assert out is not None
    assert out.metrics["makespan"] == 12


def test_ward_mix_adds_clean_when_grade_changes():
    world = {
        "family": "ward",
        "data": {"patients": [
            {"id": "A", "arrive": 0, "limit": 10, "stay": 4, "iso": True, "grade": "甲"},
            {"id": "B", "arrive": 0, "limit": 5, "stay": 4, "iso": True, "grade": "乙"},
        ]},
        "modules": {"clean": {"minutes": 2}, "mix": {"extra": 4}, "doctor": {"at": 0, "early": 0}},
        "objective": ["excess", "late_n"],
        "questions": ward.FAMILY.questions(),
        "background": [],
    }
    out = ward.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    assert out.metrics == {"excess": 5, "late_n": 1}


def test_gate_second_remote_in_a_wave_pays_extra():
    world = {
        "family": "gate",
        "data": {
            "flights": [
                {"id": "A", "arr": 0, "dep": 10, "wide": False, "pax": 10},
                {"id": "B", "arr": 0, "dep": 20, "wide": False, "pax": 10},
            ],
            "gates": [
                {"id": "G1", "remote": True, "bus": 2, "adj": []},
                {"id": "G2", "remote": True, "bus": 2, "adj": []},
            ],
        },
        "modules": {"wave": {"width": 30, "extra": 5}},
        "objective": ["pax_bus", "remote_n"],
        "questions": gate.FAMILY.questions(),
        "background": [],
    }
    out = gate.FAMILY.simulate(world, ("G1", "G2"))
    assert out is not None
    assert out.metrics == {"pax_bus": 90, "remote_n": 2}


def test_scenes10_each_family_once_and_greedy_scores_four():
    expected = {
        "delivery": "delivery",
        "trip": "trip",
        "elevator": "elevator",
        "signal": "signal",
        "deice": "deice",
        "line": "line",
        "gate": "gate",
        "kitchen": "kitchen",
        "charge": "charge",
        "ward": "ward",
    }
    families = set()
    for name, fam_id in expected.items():
        world = json.loads((SCENES / f"{name}.json").read_text(encoding="utf-8"))
        assert world["family"] == fam_id
        families.add(fam_id)
        if fam_id in {"delivery", "trip", "elevator"}:
            continue
        fam = family_of(world)
        sol = core.solve(fam, world)
        assert sol.status == "ok"
        key = core.answers(fam, world)
        ref = answers.reference_text(world, key, core.Solver(fam), best=sol.best)
        assert answers.score(fam, world, key, ref, best=sol.best)["passed"]
        assert render.leaks(render.render_prompt(fam, world)) == []
        assert _greedy_scores_four(fam, world, sol, key)
    assert families == set(expected.values())


def _greedy_scores_four(fam, world, sol, key) -> bool:
    cf_world = fam.counterfactuals[fam.cf_key].transform(world)
    for gplan in fam.greedies(world):
        if not gplan:
            continue
        gout = fam.simulate(world, gplan)
        gcf = fam.simulate(cf_world, gplan)
        if gout is None or gcf is None:
            continue
        parts = []
        for q in world["questions"]:
            if q.get("type") == "plan":
                parts.append("-".join(gplan))
            elif q.get("cf"):
                parts.append(str(gcf.metrics[fam.primary]))
            else:
                parts.append(str(gout.metrics[q["metric"]]))
        scored = answers.score(fam, world, key, "ANSWER: " + "; ".join(parts), best=sol.best)
        if scored["points"] == 4:
            return True
    return False
