"""产线换型：一条产线按顺序加工批次，换型分钟取决于前后产品族。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选批次顺序",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_fixture(p, _w):
    return (f"共用夹具已就位：产品族 {p['pair'][0]} 紧接着换成 {p['pair'][1]} 时，这次换型分钟改为 0。"
            "其他相邻族仍按换型表。")


MODULES = {m.id: m for m in [
    Module("fixture", "共用夹具", 10, _t_fixture),
]}

METRICS = {
    "tardiness": "总逾期分钟（各批次完工时刻超出交期的部分之和，提前完工记 0）",
    "changes": "换型次数",
}

OBJECTIVE_PHRASES = {
    "tardiness": "总逾期分钟最小",
    "changes": "换型次数最小",
}


def _no_fixture(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("fixture", None)
    return x


COUNTERFACTUALS = {
    "no_fixture": Counterfactual(_no_fixture, lambda _w: "若共用夹具未就位、换型分钟恢复原表，"),
}

READINGS: dict = {}


def _setup(world: dict, prev: str, nxt: str) -> int:
    fix = world["modules"].get("fixture")
    if fix and [prev, nxt] == fix["pair"]:
        return 0
    return world["data"]["setup"][prev][nxt]


def greedy_due(world: dict) -> tuple:
    jobs = world["data"]["jobs"]
    return tuple(j["id"] for j in sorted(jobs, key=lambda j: (j["due"], j["id"])))


class LineFamily:
    id = "line"
    primary = "tardiness"
    shared = "changes"
    cf_key = "no_fixture"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_due(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 1 and "A" <= p <= "H" for p in plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [j["id"] for j in world["data"]["jobs"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        jobs = {j["id"]: j for j in world["data"]["jobs"]}
        if len(plan) != len(jobs) or set(plan) != set(jobs):
            return None
        clock = 0
        prev = "IDLE"
        changes = tardiness = 0
        fired: set[str] = set()
        for pid in plan:
            job = jobs[pid]
            su = _setup(world, prev, job["family"])
            if su == 0 and "fixture" in world["modules"] and [prev, job["family"]] == world["modules"]["fixture"]["pair"]:
                fired.add("fixture")
            if prev != "IDLE" and job["family"] != prev:
                changes += 1
            clock += su + job["minutes"]
            if clock > job["due"]:
                tardiness += clock - job["due"]
            prev = job["family"]
        return Outcome(tuple(plan), {"tardiness": tardiness, "changes": changes}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        jobs = [[j["id"], j["family"], j["minutes"], j["due"]] for j in d["jobs"]]
        setup = [[a, b, d["setup"][a][b]] for a in d["setup"] for b in d["setup"][a]]
        return "\n".join([
            "你排一条产线的批次顺序。产线同一时刻只加工一个批次，做完才能换下一个。0 分钟产线空闲，产品族记为 IDLE。",
            f"批次表每行 `[编号, 产品族, 加工分钟, 交期]`：{_c(jobs)}。",
            f"换型表每行 `[前一族, 后一族, 分钟]`：{_c(setup)}。加工前先花掉这次换型分钟，再加工。",
            "换型次数只计相邻两个批次产品族不同的次数。从 IDLE 进入第一个批次的准备分钟计入完工时刻，但不计次。",
            "完工时刻晚于交期的部分记入总逾期；不晚于交期则该批次逾期为 0。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "tardiness", "points": 6,
             "text": "给出最优批次顺序，批次编号用短横线连接，例如 A-B-C-D-E-F。"},
            {"name": "tardiness", "metric": "tardiness", "points": 5},
            {"name": "changes", "metric": "changes", "points": 4},
            {"name": "cf_tardiness", "metric": "tardiness", "points": 5, "cf": "no_fixture"},
        ]


FAMILY = LineFamily()
