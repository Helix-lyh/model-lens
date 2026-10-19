"""后厨出餐：两口灶，决定菜品占灶顺序。同桌的菜要一起上，先出锅的菜在出餐口保温，超时变质。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome
from eval_bank_20260925.worldkit.share import dual_progress

DECISIONS = ("选占灶顺序",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_rush(p, _w):
    ids = "、".join(p["ids"])
    return f"催菜加火：菜品 {ids} 的占灶分钟各增加 {p['extra']} 分钟。其他菜的占灶分钟不变。"


def _t_pan(p, _w):
    return (f"换锅：同一口灶上，下一道菜的锅型与刚出锅的不同时，该灶要空等 {p['minutes']} 分钟才能开工。"
            "锅型相同，或这口灶还没做过菜，出锅后立刻可以开工。"
            "换锅的空等不计入占灶分钟。两口灶各自计算。")


def _t_gas(_p, _w):
    return ("并灶：两口灶都在占灶的每一分钟，两道菜都只累积半格，同一道菜累积满 2 分钟才算完成 1 个占灶单位。"
            "某一分钟只有一口灶在占灶时，这道菜该分钟完成 1 个占灶单位，此前未满的半格清零。")


MODULES = {m.id: m for m in [
    Module("rush", "催菜", 10, _t_rush),
    Module("pan", "换锅", 20, _t_pan),
    Module("gas", "并灶", 30, _t_gas),
]}

METRICS = {
    "makespan": "最晚出锅分钟",
    "flow": "总出锅分钟（各菜出锅时刻之和）",
    "on_time": "没有菜变质的桌数",
    "spoils": "变质盘数",
}

OBJECTIVE_PHRASES = {
    "makespan": "最晚出锅分钟最小",
    "flow": "总出锅分钟最小",
    "spoils": "变质盘数最小",
}


def _no_rush(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("rush", None)
    return x


def _pan_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    pan = x["modules"]["pan"]
    x["modules"]["pan"] = {**pan, "minutes": pan["alt"]}
    return x


COUNTERFACTUALS = {
    "no_rush": Counterfactual(_no_rush, lambda _w: "若不再催菜加火、占灶分钟恢复原值，"),
    "pan_shift": Counterfactual(
        _pan_shift,
        lambda w: f"若换锅空等改为 {w['modules']['pan']['alt']} 分钟（其余不变），",
    ),
}

READINGS: dict = {}


def _cook(world: dict, dish: dict) -> int:
    rush = world["modules"].get("rush")
    extra = rush["extra"] if rush and dish["id"] in rush["ids"] else 0
    return dish["cook"] + extra


def _hold(world: dict, dish: dict) -> int:
    return dish["hold"]


def _finish_map(world: dict, plan: tuple) -> tuple[dict[str, int], bool] | None:
    dishes = {d["id"]: d for d in world["data"]["dishes"]}
    if len(plan) != len(dishes) or set(plan) != set(dishes):
        return None
    gap = world["modules"]["pan"]["minutes"] if "pan" in world["modules"] else 0
    share = "gas" in world["modules"]
    free = [0, 0]
    last: list[str | None] = [None, None]
    starts: list[int] = []
    stoves: list[int] = []
    needs: list[int] = []
    pids: list[str] = []
    used = False
    done: list[int] = []
    for pid in plan:
        dish = dishes[pid]

        def avail(b: int, dish=dish) -> int:
            if gap and last[b] not in (None, dish["pan"]):
                return free[b] + gap
            return free[b]

        b = 0 if avail(0) <= avail(1) else 1
        if gap and last[b] not in (None, dish["pan"]):
            used = True
        start = avail(b)
        pids.append(pid)
        starts.append(start)
        stoves.append(b)
        needs.append(_cook(world, dish))
        if share:
            done = dual_progress(starts, stoves, needs, True)
        else:
            done = [s + n for s, n in zip(starts, needs)]
        free = [0, 0]
        last = [None, None]
        for i, end in enumerate(done):
            sid = stoves[i]
            free[sid] = max(free[sid], end)
            last[sid] = dishes[pids[i]]["pan"] if gap else last[sid]
    return {pid: end for pid, end in zip(pids, done)}, used


def greedy_short(world: dict) -> tuple:
    """先做快手菜。"""
    dishes = world["data"]["dishes"]
    return tuple(d["id"] for d in sorted(dishes, key=lambda d: (_cook(world, d), d["id"])))


def greedy_table(world: dict) -> tuple:
    """按桌做完再换桌，同桌先做占灶更长的。"""
    dishes = world["data"]["dishes"]
    return tuple(d["id"] for d in sorted(dishes, key=lambda d: (d["table"], -_cook(world, d), d["id"])))


def greedy_long(world: dict) -> tuple:
    """先做占灶更长的菜。不计换锅。"""
    dishes = world["data"]["dishes"]
    return tuple(d["id"] for d in sorted(dishes, key=lambda d: (-_cook(world, d), d["id"])))


def _greedies(world: dict) -> list[tuple]:
    out = [greedy_short(world), greedy_table(world)]
    if "pan" in world["modules"]:
        out.insert(0, greedy_long(world))
    return out


class KitchenFamily:
    id = "kitchen"
    primary = "flow"
    shared = "on_time"
    cf_key = "no_rush"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(_greedies)

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 1 and "A" <= p <= "H" for p in plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [d["id"] for d in world["data"]["dishes"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        mapped = _finish_map(world, plan)
        if mapped is None:
            return None
        finishes, used_pan = mapped
        dishes = {d["id"]: d for d in world["data"]["dishes"]}
        tables: dict[str, list[str]] = {}
        for d in world["data"]["dishes"]:
            tables.setdefault(d["table"], []).append(d["id"])
        spoils = on_time = 0
        fired: set[str] = set()
        rush = world["modules"].get("rush")
        if used_pan:
            fired.add("pan")
        if "gas" in world["modules"]:
            fired.add("gas")
        for members in tables.values():
            done = max(finishes[i] for i in members)
            bad = False
            for i in members:
                if done - finishes[i] > _hold(world, dishes[i]):
                    spoils += 1
                    bad = True
                    if rush and i in rush["ids"]:
                        fired.add("rush")
            if not bad:
                on_time += 1
        makespan = max(finishes.values())
        return Outcome(tuple(plan), {
            "makespan": makespan, "flow": sum(finishes.values()), "on_time": on_time, "spoils": spoils,
        }, [], frozenset(fired))

    def header(self, world: dict) -> str:
        panned = "pan" in world["modules"]
        gas = "gas" in world["modules"]
        if panned:
            rows = [[d["id"], d["table"], d["cook"], d["hold"], d["pan"]] for d in world["data"]["dishes"]]
            table = f"菜品表每行 `[编号, 桌号, 占灶分钟, 保温分钟, 锅型]`：{_c(rows)}。表中的占灶分钟是加火之前的数值。"
            place = "每道菜放到当前开工更早的灶上；换锅空等见规则。两口灶开工时刻相同时放 1 号灶。"
        else:
            rows = [[d["id"], d["table"], d["cook"], d["hold"]] for d in world["data"]["dishes"]]
            table = f"菜品表每行 `[编号, 桌号, 占灶分钟, 保温分钟]`：{_c(rows)}。表中的占灶分钟是加火之前的数值。"
            place = "每道菜放到当前更早空出的灶上；两口灶同时空出时放 1 号灶。开始时刻就是该灶空出的时刻。"
        if not gas:
            place += "出锅时刻等于开工时刻加上占灶分钟。"
        return "\n".join([
            "你是出餐口。两口灶从 0 分钟起可用，决定菜品开始占灶的顺序。",
            table,
            place,
            "同一桌的菜一起上，上桌时刻 = 该桌最晚出锅的时刻。先出锅的菜在出餐口等待，等待分钟 = 上桌时刻 − 出锅时刻。等待大于保温分钟则这盘变质。",
            "没有菜变质的桌计入准时桌。总出锅分钟是各菜出锅时刻之和。最晚出锅分钟是这些出锅时刻的最大值。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "flow", "points": 6,
             "text": "给出最优占灶顺序，菜品编号用短横线连接，例如 A-B-C-D-E-F。"},
            {"name": "flow", "metric": "flow", "points": 5},
            {"name": "on_time", "metric": "on_time", "points": 4},
            {"name": "cf_flow", "metric": "flow", "points": 5, "cf": "no_rush"},
        ]


FAMILY = KitchenFamily()
