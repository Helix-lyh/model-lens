"""港口泊位：两泊位加一艘拖轮。方案同时选定靠泊泊位和拖轮服务顺序。"""
from __future__ import annotations

import copy
import itertools
import json
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选泊位", "选靠泊顺序")


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_tide(p, _w):
    return (f"潮汐：编号 {p['berth']} 的泊位在第 {p['lo']} 分钟起、到第 {p['hi']} 分钟之前不能开始靠泊。"
            "已经开始的靠泊不中断。其他泊位不受潮汐限制。")


def _t_flush(p, _w):
    return (f"清舱：同一泊位上，后一艘船的货种与刚离开的不同时，作业开始前加 {p['minutes']} 分钟清舱。"
            "货种相同、或该泊位还没有接待过船，不加清舱。清舱期间拖轮已经离开，泊位仍被占用。")


def _t_swell(p, _w):
    return f"涌浪：每艘船的作业分钟在表中数值上再加 {p['extra']} 分钟。清舱和拖轮分钟不加。"


MODULES = {m.id: m for m in [
    Module("tide", "潮汐", 10, _t_tide),
    Module("flush", "清舱", 15, _t_flush),
    Module("swell", "涌浪", 20, _t_swell),
]}

METRICS = {
    "tardiness": "总逾期分钟（各船离泊时刻超出时限的部分之和，提前离泊记 0）",
    "late_n": "逾期船数",
}

OBJECTIVE_PHRASES = {
    "tardiness": "总逾期分钟最小",
    "late_n": "逾期船数最小",
}


def _no_swell(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("swell", None)
    return x


COUNTERFACTUALS = {
    "no_swell": Counterfactual(_no_swell, lambda _w: "若没有涌浪、作业分钟恢复为表中数值，"),
}

READINGS: dict = {}


def _parse(plan: tuple, ships: dict, berths: dict) -> list[tuple[str, str]] | None:
    if len(plan) != len(ships):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 2 or tok[0] not in ships or tok[1] not in berths:
            return None
        if tok[0] in seen:
            return None
        seen.add(tok[0])
        out.append((tok[0], tok[1]))
    if seen != set(ships):
        return None
    return out


def greedy_due(world: dict) -> tuple:
    """按时限紧的先靠，能进深水就进深水。不计拖轮排队和潮汐。"""
    berths = sorted(world["data"]["berths"], key=lambda b: (-b["length"], b["id"]))
    ships = sorted(world["data"]["ships"], key=lambda s: (s["due"], s["id"]))
    plan = []
    for ship in ships:
        fit = next(b for b in berths if b["length"] >= ship["length"])
        plan.append(ship["id"] + fit["id"])
    return tuple(plan)


class QuayFamily:
    id = "quay"
    primary = "tardiness"
    shared = "late_n"
    cf_key = "no_swell"
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
        if not all(len(p) == 2 and "A" <= p[0] <= "H" and p[1] in "12" for p in plan):
            return None
        if len({p[0] for p in plan}) != len(plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [s["id"] for s in world["data"]["ships"]]
        berth_ids = [b["id"] for b in world["data"]["berths"]]
        for order in itertools.permutations(ids):
            for assign in itertools.product(berth_ids, repeat=len(ids)):
                yield tuple(s + b for s, b in zip(order, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        return _simulate(world, plan)

    def header(self, world: dict) -> str:
        d = world["data"]
        berths = [[b["id"], b["length"]] for b in d["berths"]]
        ships = [[s["id"], s["length"], s["arrive"], s["work"], s["due"], s["cargo"]] for s in d["ships"]]
        return "\n".join([
            "你是港口调度。两条泊位、一艘引水拖轮，决定每艘船靠哪条泊位，以及拖轮服务的先后。",
            f"泊位表每行 `[编号, 可停最大船长]`：{_c(berths)}。",
            f"船舶表每行 `[编号, 船长, 到港分钟, 作业分钟, 离港时限, 货种]`：{_c(ships)}。",
            f"拖轮同时只服务一艘船。靠泊开始时刻 = max(到港分钟, 拖轮空闲分钟, 该泊位空闲分钟)。"
            f"靠泊占用拖轮 {d['tug']} 分钟，期间泊位也被占用。船长超过该泊位上限则方案不可行。",
            "离泊时刻 = 靠泊开始 + 拖轮分钟 + 清舱分钟 + 作业分钟。离泊后泊位立刻空出，拖轮在靠泊结束时就空出。"
            "逾期分钟 = max(0, 离泊时刻 − 离港时限)。",
            "答题记号：每艘船写「编号+泊位编号」，按拖轮服务先后用短横线连接，例如 A1-B2-C1。每艘船恰好出现一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "tardiness", "points": 6,
             "text": "给出最优方案，记号如 A1-B2-C1。"},
            {"name": "tardiness", "metric": "tardiness", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_tardiness", "metric": "tardiness", "points": 5, "cf": "no_swell"},
        ]


FAMILY = QuayFamily()


def _simulate(world: dict, plan: tuple) -> Outcome | None:
    ships = {s["id"]: s for s in world["data"]["ships"]}
    berths = {b["id"]: b for b in world["data"]["berths"]}
    parsed = _parse(plan, ships, berths)
    if parsed is None:
        return None
    tug = world["data"]["tug"]
    mods = world["modules"]
    tide = mods.get("tide")
    flush_min = mods["flush"]["minutes"] if "flush" in mods else 0
    extra = mods["swell"]["extra"] if "swell" in mods else 0
    tug_free = 0
    berth_free = {b: 0 for b in berths}
    last_cargo: dict[str, str | None] = {b: None for b in berths}
    tardiness = late_n = 0
    fired: set[str] = set()
    for sid, bid in parsed:
        ship = ships[sid]
        if ship["length"] > berths[bid]["length"]:
            return None
        start = max(ship["arrive"], tug_free, berth_free[bid])
        if tide and bid == tide["berth"] and tide["lo"] <= start < tide["hi"]:
            start = tide["hi"]
            fired.add("tide")
        tug_free = start + tug
        flush = 0
        if flush_min and last_cargo[bid] is not None and last_cargo[bid] != ship["cargo"]:
            flush = flush_min
            fired.add("flush")
        leave = start + tug + flush + ship["work"] + extra
        berth_free[bid] = leave
        last_cargo[bid] = ship["cargo"]
        over = leave - ship["due"]
        if over > 0:
            tardiness += over
            late_n += 1
    if extra:
        fired.add("swell")
    return Outcome(tuple(plan), {"tardiness": tardiness, "late_n": late_n}, [], frozenset(fired))
