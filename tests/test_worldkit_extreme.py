"""三道极难：贪心或就近方案可行，但到达/等待和车费或最长等待都不是最优。"""
from __future__ import annotations

import copy

from eval_bank_20260925.worldkit import answers as ans
from eval_bank_20260925.worldkit import core, render
from eval_bank_20260925.worldkit.families import delivery, elevator, trip

def test_trip_extreme_greedy_misses_arrive_and_fare():
    world = trip.extreme_world()
    sol = core.solve(trip.FAMILY, world)
    assert sol.status == "ok"
    assert sol.n_plans == 6 ** 4
    greedy = trip.greedy_leg_plan(world)
    gout = trip.FAMILY.simulate(world, greedy)
    assert gout is not None
    assert gout.plan != sol.best.plan
    assert gout.metrics["arrive"] != sol.best.metrics["arrive"]
    assert gout.metrics["fare"] != sol.best.metrics["fare"]
    dry = copy.deepcopy(world)
    dry["modules"].pop("rain")
    dsol = core.solve(trip.FAMILY, dry)
    assert dsol.best.metrics["arrive"] != sol.best.metrics["arrive"]
    prompt = render.render_prompt(trip.FAMILY, world)
    assert "选交通工具" in prompt and "选路" in prompt
    assert not render.leaks(prompt)
    key = core.answers(trip.FAMILY, world)
    text = ans.reference_text(world, key, core.Solver(trip.FAMILY), best=sol.best)
    assert ans.score(trip.FAMILY, world, key, text, best=sol.best)["passed"]


def test_elevator_extreme_high_then_return_misses_both_waits():
    world = elevator.extreme_world()
    sol = core.solve(elevator.FAMILY, world)
    assert sol.status == "ok"
    assert sol.n_feasible >= 15
    trap = elevator.high_then_return_plan(world)
    tout = elevator.FAMILY.simulate(world, trap)
    assert tout is not None
    assert trap != sol.best.plan
    assert tout.metrics["total_wait"] != sol.best.metrics["total_wait"]
    assert tout.metrics["max_wait"] != sol.best.metrics["max_wait"]
    prompt = render.render_prompt(elevator.FAMILY, world)
    assert "选单" in prompt and "选顺序" in prompt and "禁停" in prompt
    assert not render.leaks(prompt)
    key = core.answers(elevator.FAMILY, world)
    text = ans.reference_text(world, key, core.Solver(elevator.FAMILY), best=sol.best)
    assert ans.score(elevator.FAMILY, world, key, text, best=sol.best)["passed"]


def test_delivery_extreme_deadline_greedy_changes_late_count():
    world = delivery.extreme_world()
    from eval_bank_20260925.worldkit import accel, depth

    st = accel.status(world, max_plans=400_000, seconds=60)
    assert st.get("status") == "ok"
    gout = delivery.FAMILY.simulate(delivery.FAMILY.effective(world), depth.deadline_plan(world))
    assert gout is not None
    assert abs(gout.metrics["late_n"] - int(st["late_n"])) >= 2
    assert gout.metrics["total"] != int(st["total"])
    assert len(world["questions"]) == 4
    prompt = render.render_prompt(delivery.FAMILY, world)
    assert not render.leaks(prompt)
