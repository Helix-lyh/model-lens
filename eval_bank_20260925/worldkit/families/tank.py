"""罐区加注：两条鹤管共用一只储罐。罐空了要整罐补液，期间两臂都停。决定车辆顺序。"""
from __future__ import annotations

import copy
import itertools
import json
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选加注顺序",)


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_tank(p, _w):
    return (f"储罐：两臂从同一只罐抽。罐开始有 {p['cap']} 个单位。"
            "某一分钟若有车在加注，甲臂先取 1 个单位，乙臂再取 1 个单位；罐里剩几个取几个。"
            f"一分钟开始时罐是空的，就立刻补液 {p['refill']} 分钟，补液期间两臂都不出液，补完罐回到 {p['cap']} 个单位再继续。"
            "补液不把已经挂上的车卸下来。")


def _t_block(p, _w):
    return (f"甲臂检修：第 {p['lo']} 分钟起、到第 {p['hi']} 分钟之前，甲臂不出液。"
            "挂在甲臂上的车这一段时间液量不变。乙臂照常，罐该怎么抽怎么抽。"
            "检修不推迟挂枪，车可以挂在甲臂上干等。")


def _t_extra(p, _w):
    return f"加注加量：每辆车要加的单位在表中数值上再加 {p['extra']} 个。储罐和补液仍按加完之后的单位计算。"


MODULES = {m.id: m for m in [
    Module("tank", "储罐", 10, _t_tank),
    Module("block", "甲臂检修", 15, _t_block),
    Module("extra", "加注加量", 20, _t_extra),
]}

METRICS = {
    "late": "总迟到分钟（各车加满时刻超出出发时刻的部分之和，提前加满记 0）",
    "late_n": "迟到车辆数",
}

OBJECTIVE_PHRASES = {
    "late": "总迟到分钟最小",
    "late_n": "迟到车辆数最小",
}


def _no_extra(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("extra", None)
    return x


COUNTERFACTUALS = {
    "no_extra": Counterfactual(_no_extra, lambda _w: "若取消加注加量、单位恢复为表中数值，"),
}

READINGS: dict = {}


def _simulate(starts: list[int], arms: list[int], needs: list[int],
              cap: int, refill: int, block: tuple[int, int] | None) -> list[int]:
    n = len(starts)
    got = [0] * n
    done = [-1] * n
    left = n
    t = 0
    tank = cap
    refill_until = -1
    lo, hi = block if block else (1, 0)
    while left:
        if refill_until > t:
            t = refill_until
            tank = cap
            continue
        active: list[int] = []
        for i in range(n):
            if done[i] >= 0 or starts[i] > t:
                continue
            if arms[i] == 0 and lo <= t < hi:
                continue
            active.append(i)
        if not active:
            nxt = None
            for i in range(n):
                if done[i] < 0 and (nxt is None or starts[i] < nxt):
                    nxt = starts[i]
            if nxt is None or nxt <= t:
                nxt = t + 1
            if lo <= t < hi and nxt > hi:
                t = hi
            elif refill_until > t and (nxt is None or refill_until <= nxt):
                t = refill_until
            else:
                t = nxt
            continue
        if tank == 0:
            refill_until = t + refill
            continue
        active.sort(key=lambda i: (arms[i], i))
        for i in active:
            if tank == 0:
                break
            tank -= 1
            got[i] += 1
            if got[i] >= needs[i]:
                done[i] = t + 1
                left -= 1
        t += 1
        if t > 20000:
            raise RuntimeError("tank simulation did not finish")
    return done


def greedy_depart(world: dict) -> tuple:
    cars = world["data"]["cars"]
    return tuple(c["id"] for c in sorted(cars, key=lambda c: (c["depart"], c["id"])))


class TankFamily:
    id = "tank"
    primary = "late"
    shared = "late_n"
    cf_key = "no_extra"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_depart(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 1 and "A" <= p <= "H" for p in plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [c["id"] for c in world["data"]["cars"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        cars = {c["id"]: c for c in world["data"]["cars"]}
        if len(plan) != len(cars) or set(plan) != set(cars):
            return None
        extra = world["modules"]["extra"]["extra"] if "extra" in world["modules"] else 0
        spec = world["modules"]["tank"]
        window = world["modules"].get("block")
        block = (window["lo"], window["hi"]) if window else None
        starts: list[int] = []
        arms: list[int] = []
        needs: list[int] = []
        fired: set[str] = set()
        free = [0, 0]
        for pid in plan:
            car = cars[pid]
            b = 0 if free[0] <= free[1] else 1
            starts.append(free[b])
            arms.append(b)
            needs.append(car["need"] + extra)
            done = _simulate(starts, arms, needs, spec["cap"], spec["refill"], block)
            if block and any(arms[i] == 0 and starts[i] < block[1] and done[i] > block[0] for i in range(len(starts))):
                fired.add("block")
            if any(done[i] > starts[i] + needs[i] for i in range(len(starts))):
                fired.add("tank")
            free = [0, 0]
            for i, end in enumerate(done):
                free[arms[i]] = max(free[arms[i]], end)
        late = late_n = 0
        for pid, end in zip(plan, done):
            over = end - cars[pid]["depart"]
            if over > 0:
                late += over
                late_n += 1
        if extra:
            fired.add("extra")
        return Outcome(tuple(plan), {"late": late, "late_n": late_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        rows = [[c["id"], c["need"], c["depart"]] for c in world["data"]["cars"]]
        return "\n".join([
            "你给危化品罐区排加注顺序。两条鹤管从 0 分钟起空闲，甲臂和乙臂抽同一只储罐。",
            f"车辆表每行 `[编号, 需要的单位, 出发分钟]`：{_c(rows)}。车辆 0 分钟已在场，可以立即挂枪。",
            "每辆车挂到当前更早空闲的臂上；两臂同时空闲时挂甲臂。挂枪时刻就是该臂空闲的时刻，加满后该臂立刻空出。",
            "罐里有液时，一条臂一分钟给所挂的车 1 个单位。迟到分钟 = max(0, 加满时刻 − 出发分钟)。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "late", "points": 6,
             "text": "给出最优加注顺序，车辆编号用短横线连接，例如 A-B-C-D-E-F。"},
            {"name": "late", "metric": "late", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_late", "metric": "late", "points": 5, "cf": "no_extra"},
        ]


FAMILY = TankFamily()
