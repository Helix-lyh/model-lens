"""二十道极难：五道已有扩展题加十五道分段选择。分段手算一条，冻结题的逐段贪心恰好 4 分。"""
import json
from pathlib import Path

from eval_bank_20260925.worldkit import answers, core, render
from eval_bank_20260925.worldkit.families import family_of
from eval_bank_20260925.worldkit.families.cascade import FAMILIES
from eval_bank_20260925.worldkit.families.changeover import FAMILIES as CHANGEOVER

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "eval_bank_20260925/worldkit/worlds/scenes20"
KEEP = ("delivery", "trip", "elevator", "signal", "line")


def test_changeover_counts_a_switch_even_when_minutes_are_zero():
    fam = CHANGEOVER["or"]
    world = {
        "family": "or",
        "data": {
            "jobs": [
                {"id": "A", "family": "W", "minutes": 5, "due": 100},
                {"id": "B", "family": "X", "minutes": 5, "due": 100},
            ],
            "setup": {
                "IDLE": {"W": 1, "X": 1},
                "W": {"W": 4, "X": 9},
                "X": {"W": 9, "X": 4},
            },
        },
        "modules": {"fixture": {"pair": ["W", "X"]}},
        "objective": ["tardiness", "changes"],
        "questions": fam.questions(),
        "background": [],
    }
    out = fam.simulate(world, ("A", "B"))
    assert out is not None
    assert out.metrics == {"tardiness": 0, "changes": 1}


def test_cascade_doubles_a_segment_then_waits_at_the_next_light():
    fam = FAMILIES["or"]
    leg = {
        "CREW": {"DIRECT": [{"min": 4, "lights": True}], "DETOUR": [{"min": 9}]},
        "BLOCK": {"DIRECT": [{"min": 10, "lights": True}], "DETOUR": [{"min": 14}]},
        "VEND": {"DIRECT": {"access": 1, "ride": 4}, "DETOUR": {"access": 2, "ride": 6}},
    }
    world = {
        "family": "or",
        "data": {
            "modes": [
                {"id": "CREW", "label": "连台班", "kind": "fast"},
                {"id": "BLOCK", "label": "封闭班", "kind": "plain"},
                {"id": "VEND", "label": "外包班", "kind": "timed"},
            ],
            "routes": [{"id": "DIRECT", "label": "直达"}, {"id": "DETOUR", "label": "绕行"}],
            "cost": {"CREW": 2, "BLOCK": 0, "VEND": 3},
            "legs": [{**leg, "name": "甲"}, {**leg, "name": "乙"}],
        },
        "modules": {
            "surge": {"ids": ["CREW"], "factor": 2},
            "wave": {"ids": ["CREW", "BLOCK"], "cycle": 10, "open": 4},
        },
        "objective": ["time", "cost"],
        "questions": fam.questions(),
        "background": [],
    }
    crew = fam.simulate(world, ("CREW", "DIRECT", "CREW", "DIRECT"))
    assert crew is not None
    assert crew.metrics == {"time": 18, "cost": 4}
    assert "wave" in crew.fired and "surge" in crew.fired
    assert fam.local_clock(world, ("CREW", "DIRECT", "CREW", "DIRECT")) == 16


def test_scenes20_has_twenty_distinct_families_and_greedy_scores_four():
    names = list(KEEP) + list(FAMILIES)
    assert len(names) == 20
    seen = set()
    for name in names:
        world = json.loads((SCENES / f"{name}.json").read_text(encoding="utf-8"))
        assert world["family"] == name
        seen.add(name)
        if name in {"delivery", "trip", "elevator"}:
            continue
        fam = family_of(world)
        sol = core.solve(fam, world)
        assert sol.status == "ok"
        key = core.answers(fam, world)
        ref = answers.reference_text(world, key, core.Solver(fam), best=sol.best)
        assert answers.score(fam, world, key, ref, best=sol.best)["passed"]
        assert render.leaks(render.render_prompt(fam, world)) == []
        if name not in KEEP:
            assert _greedy_scores_four(fam, world, sol, key)
            assert _local_sum_scores_four(fam, world, sol, key)
    assert seen == set(names)


def _local_sum_scores_four(fam, world, sol, key) -> bool:
    plan = fam.greedies(world)[0]
    out = fam.simulate(world, plan)
    bare = fam.counterfactuals[fam.cf_key].transform(world)
    local = fam.local_clock(world, plan)
    local_cf = fam.local_clock(bare, plan)
    text = "ANSWER: " + "; ".join(["-".join(plan), str(local), str(out.metrics["cost"]), str(local_cf)])
    return answers.score(fam, world, key, text, best=sol.best)["points"] == 4


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
