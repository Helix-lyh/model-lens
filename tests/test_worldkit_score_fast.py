"""plan 题传 best 时不应再调用 Solver 全枚举。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

import pytest

from eval_bank_20260925.worldkit import answers as ans
from eval_bank_20260925.worldkit import core


@dataclass
class _TinyFamily:
    """极小题族：方案指标查表，不实现 plans 枚举。"""

    id: str = "tiny"
    modules: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=lambda: {"total": "总时长"})
    counterfactuals: dict = field(default_factory=dict)
    readings: dict = field(default_factory=dict)

    def effective(self, world: dict) -> dict:
        return world

    def active_orders(self, live: dict) -> list[str]:
        return sorted(live["data"]["orders"])

    def plans(self, live: dict) -> Iterator[tuple[str, ...]]:
        yield from ()

    def simulate(self, live: dict, plan: tuple[str, ...]) -> core.Outcome | None:
        spec = live["data"]["plans"].get("-".join(plan))
        if spec is None:
            return None
        return core.Outcome(plan, dict(spec), [], frozenset())

    def header(self, world: dict) -> str:
        return ""

    def objective_text(self, world: dict) -> str:
        return ""


class _BoomSolver:
    def __call__(self, world: dict) -> Any:
        raise AssertionError("solver 不应在传 best 时被调用")


def _world() -> dict:
    return {
        "family": "tiny",
        "objective": ["total"],
        "modules": {},
        "data": {
            "orders": ["A", "B"],
            "plans": {"A-B": {"total": 10}, "B-A": {"total": 20}},
        },
        "questions": [{"name": "route", "type": "plan", "points": 20, "accept": "optimal"}],
    }


@pytest.fixture
def tiny() -> _TinyFamily:
    return _TinyFamily()


@pytest.fixture
def best() -> core.Outcome:
    return core.Outcome(("A", "B"), {"total": 10}, [], frozenset())


def test_score_plan_optimal_uses_best_without_solver(tiny: _TinyFamily, best: core.Outcome) -> None:
    w = _world()
    key = {"route": 10}
    boom = _BoomSolver()

    good = ans.score(tiny, w, key, "ANSWER: A-B", boom, best=best)
    assert good["passed"] and good["points"] == 20

    bad = ans.score(tiny, w, key, "ANSWER: B-A", boom, best=best)
    assert not bad["passed"] and bad["points"] == 0


def test_reference_text_uses_best_without_solver(tiny: _TinyFamily, best: core.Outcome) -> None:
    w = _world()
    key = {"route": 10}
    ref = ans.reference_text(w, key, _BoomSolver(), best=best)
    assert ref == "ANSWER: A-B"
    assert ans.score(tiny, w, key, ref, _BoomSolver(), best=best)["passed"]
