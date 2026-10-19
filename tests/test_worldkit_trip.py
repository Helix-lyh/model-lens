"""worldkit 出行题族：冻结局面手算、下雨反事实、题面渲染。"""
from __future__ import annotations

import copy

from eval_bank_20260925.worldkit import answers as ans
from eval_bank_20260925.worldkit import core, render
from eval_bank_20260925.worldkit.families import trip

FAM = trip.FAMILY
WORLD = trip.frozen_world()


def _solve(world: dict) -> core.Solution:
    return core.solve(FAM, world)


def test_frozen_hand_computed_optimal():
    """有雨：步行绕行 12；公交直达 13 更慢；骑车直达 22。"""
    sol = _solve(WORLD)
    assert sol.status == "ok"
    assert sol.n_plans == 6 and sol.n_feasible == 6
    assert sol.best.plan == ("walk", "detour")
    assert sol.best.metrics == {"arrive": 12, "fare": 0}


def test_rain_toggles_optimal_tool_or_route():
    wet = _solve(WORLD).best.plan
    dry_world = copy.deepcopy(WORLD)
    dry_world["modules"].pop("rain")
    dry = _solve(dry_world).best.plan
    assert wet != dry
    assert wet == ("walk", "detour")
    assert dry == ("bike", "detour")


def test_counterfactual_dry_arrival_differs():
    solver = core.Solver(FAM)
    key = core.answers(FAM, WORLD, solver)
    assert key == {
        "plan": 12,
        "arrive": 12,
        "fare": 0,
        "dry_arrive": 10,
    }
    assert key["dry_arrive"] != key["arrive"]


def test_all_six_plans_hand_table():
    """与手算表一致。"""
    expect = {
        ("walk", "direct"): (15, 0),
        ("walk", "detour"): (12, 0),
        ("bike", "direct"): (22, 2),
        ("bike", "detour"): (20, 2),
        ("bus", "direct"): (13, 4),
        ("bus", "detour"): (17, 4),
    }
    live = FAM.effective(WORLD)
    for plan, (arr, fare) in expect.items():
        out = FAM.simulate(live, plan)
        assert out is not None
        assert out.metrics == {"arrive": arr, "fare": fare}


def test_prompt_renders_without_leaks():
    prompt = render.render_prompt(FAM, WORLD)
    assert "家" in prompt and "公司" in prompt
    assert "WALK-DETOUR" not in prompt
    assert not render.leaks(prompt)


def test_answer_format_in_prompt():
    prompt = render.render_prompt(FAM, WORLD)
    assert ans.answer_format(4) in prompt


def test_score_accepts_short_codes():
    solver = core.Solver(FAM)
    key = core.answers(FAM, WORLD, solver)
    best = solver(WORLD).best
    good = ans.score(FAM, WORLD, key, "ANSWER: WALK-DETOUR; 12; 0; 10", best=best)
    assert good["passed"] and good["points"] == 20
    bad = ans.score(FAM, WORLD, key, "ANSWER: BIKE-DIRECT; 12; 0; 10", best=best)
    assert bad["points"] == 14 and bad["groups"][0]["points"] == 0
