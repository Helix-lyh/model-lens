"""消防疏散：两座楼梯。方案同时选定各区域走哪座楼梯，以及放行顺序。"""
from __future__ import annotations

import copy
import itertools
import json
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选楼梯", "选放行顺序")


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_smoke(p, _w):
    return (f"烟气：编号 {p['stair']} 的楼梯在第 {p['lo']} 分钟起、到第 {p['hi']} 分钟之前不能开始进入。"
            "已经开始进入的人群继续下楼。另一座楼梯不受烟气限制。")


def _t_slow(p, _w):
    ids = "、".join(p["ids"])
    return (f"协助撤离：区域 {ids} 的每个人占用 2 个通行名额，其他区域每人占用 1 个。"
            "楼梯每分钟的通行名额见楼梯表。")


def _t_drill(p, _w):
    return f"加演：每个区域的人数在表中数值上再加 {p['extra']} 人。协助撤离的名额按加完之后的人数计算。"


MODULES = {m.id: m for m in [
    Module("smoke", "烟气", 10, _t_smoke),
    Module("slow", "协助撤离", 15, _t_slow),
    Module("drill", "加演", 20, _t_drill),
]}

METRICS = {
    "delay": "总滞留分钟（各区域全部进入楼梯的时刻超出时限的部分之和，未超出记 0）",
    "late_n": "超出时限的区域数",
}

OBJECTIVE_PHRASES = {
    "delay": "总滞留分钟最小",
    "late_n": "超出时限的区域数最小",
}


def _no_drill(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("drill", None)
    return x


COUNTERFACTUALS = {
    "no_drill": Counterfactual(_no_drill, lambda _w: "若取消加演、人数恢复为表中数值，"),
}

READINGS: dict = {}


def _parse(plan: tuple, groups: dict, stairs: dict) -> list[tuple[str, str]] | None:
    if len(plan) != len(groups):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 2 or tok[0] not in groups or tok[1] not in stairs:
            return None
        if tok[0] in seen:
            return None
        seen.add(tok[0])
        out.append((tok[0], tok[1]))
    if seen != set(groups):
        return None
    return out


def greedy_near(world: dict) -> tuple:
    """就近下楼，时限紧的先放。不计拥堵和烟气。"""
    groups = sorted(world["data"]["groups"], key=lambda g: (g["due"], g["id"]))
    plan = []
    for g in groups:
        walk = g["walk"]
        stair = min(walk, key=lambda s: (walk[s], s))
        plan.append(g["id"] + stair)
    return tuple(plan)


class EvacFamily:
    id = "evac"
    primary = "delay"
    shared = "late_n"
    cf_key = "no_drill"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_near(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 2 and "A" <= p[0] <= "H" and p[1] in "12" for p in plan):
            return None
        if len({p[0] for p in plan}) != len(plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [g["id"] for g in world["data"]["groups"]]
        stair_ids = [s["id"] for s in world["data"]["stairs"]]
        for order in itertools.permutations(ids):
            for assign in itertools.product(stair_ids, repeat=len(ids)):
                yield tuple(g + s for g, s in zip(order, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        return _simulate(world, plan)

    def header(self, world: dict) -> str:
        d = world["data"]
        stairs = [[s["id"], s["cap"]] for s in d["stairs"]]
        groups = [[g["id"], g["size"], g["walk"]["1"], g["walk"]["2"], g["due"]] for g in d["groups"]]
        return "\n".join([
            "你是商场消防总台。两座楼梯，决定每个区域走哪座楼梯，以及区域被放行的先后。",
            f"楼梯表每行 `[编号, 每分钟通行名额]`：{_c(stairs)}。",
            f"区域表每行 `[编号, 人数, 走到东梯(1)的分钟, 走到西梯(2)的分钟, 时限]`：{_c(groups)}。",
            "同一座楼梯按你写下的先后排队进入。一个区域开始进入的时刻 = max(该区域走到该楼梯的分钟, 前一个使用该楼梯的区域全部进入完毕的时刻)。"
            "进入耗时 = 该区域占用的通行名额除以该楼梯每分钟名额，不能整除则向上取整。"
            "全部进入楼梯的时刻晚于时限的部分记入总滞留。",
            "答题记号：每个区域写「编号+楼梯编号」，按放行先后用短横线连接，例如 A1-B2-C1。每个区域恰好出现一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "delay", "points": 6,
             "text": "给出最优方案，记号如 A1-B2-C1。"},
            {"name": "delay", "metric": "delay", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_delay", "metric": "delay", "points": 5, "cf": "no_drill"},
        ]


FAMILY = EvacFamily()


def _simulate(world: dict, plan: tuple) -> Outcome | None:
    groups = {g["id"]: g for g in world["data"]["groups"]}
    stairs = {s["id"]: s for s in world["data"]["stairs"]}
    parsed = _parse(plan, groups, stairs)
    if parsed is None:
        return None
    mods = world["modules"]
    smoke = mods.get("smoke")
    slow_ids = set(mods["slow"]["ids"]) if "slow" in mods else set()
    extra = mods["drill"]["extra"] if "drill" in mods else 0
    free = {s: 0 for s in stairs}
    delay = late_n = 0
    fired: set[str] = set()
    for gid, sid in parsed:
        g = groups[gid]
        size = g["size"] + extra
        slots = size * (2 if gid in slow_ids else 1)
        if gid in slow_ids:
            fired.add("slow")
        cap = stairs[sid]["cap"]
        walk = g["walk"][sid]
        start = max(walk, free[sid])
        if smoke and sid == smoke["stair"] and smoke["lo"] <= start < smoke["hi"]:
            start = smoke["hi"]
            fired.add("smoke")
        minutes = (slots + cap - 1) // cap
        done = start + minutes
        free[sid] = done
        over = done - g["due"]
        if over > 0:
            delay += over
            late_n += 1
    if extra:
        fired.add("drill")
    return Outcome(tuple(plan), {"delay": delay, "late_n": late_n}, [], frozenset(fired))
