"""worldkit 电梯题族：冻结局面手算、选顺序非就近、满员选单、反事实上限。"""
from __future__ import annotations

import itertools

from eval_bank_20260925.worldkit import answers as ans
from eval_bank_20260925.worldkit import core, render
from eval_bank_20260925.worldkit.families import elevator

FAM = elevator.FAMILY
WORLD = elevator.frozen_world()


def _solve(world: dict) -> core.Solution:
    return core.solve(FAM, world)


def test_frozen_optimal_not_nearest_floor_first():
    """0 分时刻最近等待在 2 层(P1)，最优首停须为 3 层(A 或 C)。"""
    sol = _solve(WORLD)
    assert sol.status == "ok"
    assert sol.n_plans == 120 and sol.n_feasible == 2
    assert sol.best.plan[0] in ("A", "C")
    stops = WORLD["data"]["stops"]
    assert stops[sol.best.plan[0]] == 3
    # 首停 D(2 层) 的 24 种排列均不可行或无法送完
    live = FAM.effective(WORLD)
    for rest in itertools.permutations([k for k in stops if k != "D"]):
        assert FAM.simulate(live, ("D", *rest)) is None


def test_frozen_metrics_and_lex_tiebreak():
    sol = _solve(WORLD)
    assert sol.best.metrics == {"total_wait": 47, "max_wait": 19}
    assert sol.best.plan == ("A", "B", "C", "D", "E")


def test_cap_plus_one_lowers_total_wait():
    solver = core.Solver(FAM)
    key = core.answers(FAM, WORLD, solver)
    assert key == {
        "plan": 47,
        "total_wait": 47,
        "max_wait": 19,
        "cf_total_wait": 45,
    }
    assert key["cf_total_wait"] != key["total_wait"]


def test_boarding_fifo_when_full():
    """B 停 1 层时 P3、P4 同现，cap=2 只能先上 P3；P4 等到 E 停才送达。"""
    live = FAM.effective(WORLD)
    out = FAM.simulate(live, ("A", "B", "C", "D", "E"))
    assert out is not None
    # trace: B@1 后 onboard P3,P4；C@3 下 P3；E@4 下 P4、P1
    assert out.metrics["total_wait"] == 47


def test_prompt_and_scoring():
    prompt = render.render_prompt(FAM, WORLD)
    assert elevator.DECISIONS[0] in prompt and elevator.DECISIONS[1] in prompt
    assert "支持" not in prompt
    assert not render.leaks(prompt)
    solver = core.Solver(FAM)
    key = core.answers(FAM, WORLD, solver)
    text = ans.reference_text(WORLD, key, solver)
    assert ans.score(FAM, WORLD, key, text, solver)["passed"]


def test_suboptimal_perm_infeasible_or_worse():
    live = FAM.effective(WORLD)
    sub = FAM.simulate(live, ("D", "E", "A", "B", "C"))
    assert sub is None or sub.metrics["total_wait"] > 47
