"""罐区加注：手算两条臂抽干再补液，以及猎到的世界贪心恰好 4 分。"""
import json
from pathlib import Path

from eval_bank_20260925.worldkit import answers, core, render
from eval_bank_20260925.worldkit.families import tank

ROOT = Path(__file__).resolve().parents[1]
BAND = ROOT / "eval_bank_20260925/worldkit/worlds/band10"


def _world(cars, modules):
    return {
        "family": "tank",
        "data": {"cars": cars},
        "modules": modules,
        "objective": ["late", "late_n"],
        "questions": tank.FAMILY.questions(),
        "background": [],
    }


def test_two_trucks_empty_the_tank_then_refill():
    world = _world(
        [{"id": "A", "need": 2, "depart": 5}, {"id": "B", "need": 2, "depart": 5}],
        {"tank": {"cap": 2, "refill": 3}},
    )
    out = tank.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    # 0 分两臂同时抽干；1–4 分补液；4 分各再抽 1 个，5 分加满。都不迟到。
    assert out.metrics == {"late": 0, "late_n": 0}
    late = tank.FAMILY.simulate(
        _world(
            [{"id": "A", "need": 2, "depart": 3}, {"id": "B", "need": 2, "depart": 3}],
            {"tank": {"cap": 2, "refill": 3}},
        ),
        ("A", "B"),
    )
    assert late is not None
    assert late.metrics == {"late": 4, "late_n": 2}


def test_arm_priority_gives_the_last_unit_to_arm_a():
    world = _world(
        [{"id": "A", "need": 2, "depart": 20}, {"id": "B", "need": 2, "depart": 20}],
        {"tank": {"cap": 3, "refill": 4}},
    )
    out = tank.FAMILY.simulate(world, ("A", "B"))
    assert out is not None
    # 0 分各 1，罐剩 1；1 分甲臂抽走最后 1 个并加满（时刻 2）；2–6 补液；6 分乙再抽，7 分乙满。
    assert tank._simulate([0, 0], [0, 1], [2, 2], 3, 4, None) == [2, 7]


def test_block_idles_arm_a_without_taking_from_the_tank():
    world = _world(
        [{"id": "A", "need": 2, "depart": 20}, {"id": "B", "need": 2, "depart": 20}],
        {"tank": {"cap": 10, "refill": 4}, "block": {"lo": 0, "hi": 2}},
    )
    done = tank._simulate([0, 0], [0, 1], [2, 2], 10, 4, (0, 2))
    # 甲臂 0、1 分不出液，乙臂 0、1 分加满（时刻 2）；甲臂 2、3 分加满（时刻 4）。
    assert done == [4, 2]


def _greedy_scores_four(fam, world) -> bool:
    sol = core.solve(fam, world, core.Budget(80_000, 60))
    assert sol.status == "ok"
    key = core.answers(fam, world)
    ref = answers.reference_text(world, key, core.Solver(fam), best=sol.best)
    assert answers.score(fam, world, key, ref, best=sol.best)["passed"]
    assert render.leaks(render.render_prompt(fam, world)) == []
    cf_world = fam.counterfactuals[fam.cf_key].transform(world)
    for gplan in fam.greedies(world):
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


def test_band10_tank_worlds_greedy_score_four():
    paths = sorted(BAND.glob("tank*.json"))
    if not paths:
        return
    for path in paths:
        world = json.loads(path.read_text(encoding="utf-8"))
        assert world["family"] == "tank"
        assert _greedy_scores_four(tank.FAMILY, world)
