"""worldkit 引擎：模块与题族协议、择支枚举求解、问题取值、条件消融。

世界（world）是纯 JSON 字典：
  family      题族 id
  data        题族的基础数据（路网、订单……）
  modules     {模块 id: 参数}；模块存在即规则生效，删除即规则不存在
  objective   字典序目标层（指标名，全部取最小）
  objective_conditions  {目标层: 条件名}；可被消融的目标层（删掉该层）
  questions   [{name, metric, points, cf?, type?, accept?}]
  background  在题面中出现、但不参与删除测试的模块 id（须写明理由）
"""
from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Protocol

INFEASIBLE = "无解"


class BudgetExceeded(Exception):
    pass


@dataclass(frozen=True)
class Module:
    id: str
    title: str
    stage: int
    text: Callable[[dict, dict], str]
    # effect：改变轨迹数值，须在最优轨迹上触发；constraint：限制可行方案或决策空间
    kind: str = "effect"
    ablate: Callable[[dict], dict] | None = None
    # 消融只会放大可行方案集（取消订单、互斥、随时回站的消融反而收紧）；冲突核依赖这一单调性
    relaxing: bool = True


@dataclass
class Outcome:
    plan: tuple
    metrics: dict[str, int]
    trace: list
    fired: frozenset
    boundary: int = 0


@dataclass
class Solution:
    status: str  # "ok" | "infeasible"
    best: Outcome | None
    optimal: list[Outcome]
    n_plans: int
    n_feasible: int
    n_primary: int = 0  # 主值等于最优主值的可行方案数；过大说明这个整数容易被错方案撞上
    n_shared: int = 0   # 并列指标等于最优值的可行方案数；过大说明 4 分问太粗


@dataclass(frozen=True)
class Counterfactual:
    transform: Callable[[dict], dict]
    text: Callable[[dict], str]


class Family(Protocol):
    id: str
    modules: dict[str, Module]
    metrics: dict[str, str]
    counterfactuals: dict[str, Counterfactual]
    readings: dict[str, Callable[[dict], dict | None]]

    def effective(self, world: dict) -> dict: ...
    def plans(self, world: dict) -> Iterator[tuple]: ...
    def simulate(self, world: dict, plan: tuple) -> Outcome | None: ...
    def header(self, world: dict) -> str: ...
    def objective_text(self, world: dict) -> str: ...


@dataclass
class Budget:
    max_plans: int = 200_000
    seconds: float = 20.0
    _deadline: float = field(default=0.0, repr=False)

    def start(self) -> "Budget":
        return Budget(self.max_plans, self.seconds, time.monotonic() + self.seconds)


def world_key(world: dict) -> str:
    return json.dumps(world, sort_keys=True, ensure_ascii=False)


def objective_key(world: dict, outcome: Outcome) -> tuple:
    return tuple(outcome.metrics[m] for m in world["objective"])


def solve(family: Family, world: dict, budget: Budget | None = None) -> Solution:
    budget = (budget or Budget()).start()
    live = family.effective(world)
    feasible: list[Outcome] = []
    n = 0
    for plan in family.plans(live):
        n += 1
        if n > budget.max_plans or (n % 512 == 0 and time.monotonic() > budget._deadline):
            raise BudgetExceeded(f"{n} plans")
        out = family.simulate(live, plan)
        if out is not None:
            feasible.append(out)
    if not feasible:
        return Solution("infeasible", None, [], n, 0)
    top = min(objective_key(world, o) for o in feasible)
    optimal = sorted((o for o in feasible if objective_key(world, o) == top), key=lambda o: o.plan)
    primary = getattr(family, "primary", None)
    shared = getattr(family, "shared", None)
    best_m = optimal[0].metrics
    n_primary = sum(1 for o in feasible if primary and o.metrics.get(primary) == best_m.get(primary))
    n_shared = sum(1 for o in feasible if shared and o.metrics.get(shared) == best_m.get(shared))
    return Solution("ok", optimal[0], optimal, n, len(feasible), n_primary, n_shared)


class Solver:
    """带缓存的求解器：门禁会对同一世界的大量消融变体反复求解。"""

    def __init__(self, family: Family, budget: Budget | None = None):
        self.family = family
        self.budget = budget or Budget()
        self._cache: dict[str, Solution] = {}

    def __call__(self, world: dict) -> Solution:
        k = world_key(world)
        if k not in self._cache:
            self._cache[k] = solve(self.family, world, self.budget)
        return self._cache[k]


def main_questions(world: dict) -> list[dict]:
    return [q for q in world["questions"] if not q.get("cf")]


def metric_value(sol: Solution, metric: str) -> Any:
    return INFEASIBLE if sol.status != "ok" else sol.best.metrics[metric]


def answers(family: Family, world: dict, solver: Solver | None = None) -> dict[str, Any]:
    """按 questions 取值；反事实问题对变换后的世界重新求解。"""
    solver = solver or Solver(family)
    base = solver(world)
    out: dict[str, Any] = {}
    for q in world["questions"]:
        if q.get("cf"):
            cf_world = family.counterfactuals[q["cf"]].transform(world)
            out[q["name"]] = metric_value(solver(cf_world), q["metric"])
        else:
            out[q["name"]] = metric_value(base, q["metric"])
    return out


def main_values(world: dict, sol: Solution) -> tuple:
    return tuple(metric_value(sol, q["metric"]) for q in main_questions(world))


def optimal_main_values(world: dict, sol: Solution) -> frozenset:
    """全部并列最优方案的主值集合；无解时为 {无解}。"""
    if sol.status != "ok":
        return frozenset({(INFEASIBLE,)})
    return frozenset(tuple(o.metrics[q["metric"]] for q in main_questions(world)) for o in sol.optimal)


# ---------------------------------------------------------------------------
# 条件 = 可消融的模块或目标层
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Condition:
    name: str
    ref: str  # 模块 id 或 "objective:<层>"
    apply: Callable[[dict], dict]
    relaxing: bool = True


def drop_module(world: dict, mid: str) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop(mid, None)
    return x


def _module_condition(family: Family, mid: str) -> Condition:
    m = family.modules[mid]
    fn = m.ablate or (lambda w, mid=mid: drop_module(w, mid))
    return Condition(m.title, mid, fn, m.relaxing)


def _objective_condition(layer: str, name: str) -> Condition:
    def fn(world: dict) -> dict:
        x = copy.deepcopy(world)
        x["objective"] = [m for m in x["objective"] if m != layer]
        x.get("objective_conditions", {}).pop(layer, None)
        return x
    return Condition(name, f"objective:{layer}", fn)


def conditions(family: Family, world: dict) -> list[Condition]:
    bg = set(world.get("background", []))
    out = [_module_condition(family, mid) for mid in sorted(world["modules"], key=lambda k: (family.modules[k].stage, k))
           if mid not in bg]
    out += [_objective_condition(layer, name) for layer, name in world.get("objective_conditions", {}).items()]
    return out
