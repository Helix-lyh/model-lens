"""车队充电：两根桩接在同一面配电柜上，同时充电就降为半功率。决定插枪顺序。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome
from eval_bank_20260925.worldkit.share import dual_progress

DECISIONS = ("选插枪顺序",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_share(_p, _w):
    return ("并柜：两根桩都有车的每一分钟，两车都只累积半格，同一辆车累积满 2 分钟才获得 1 个电量单位。"
            "某一分钟只有一根桩有车时，这辆车该分钟获得 1 个电量单位，此前未满的半格清零。")


def _t_topup(p, _w):
    return f"补电：每辆车要充的电量单位在表中数值上再加 {p['extra']} 个。并柜仍按加完之后的电量计算。"


def _t_block(p, _w):
    return (f"柜体检修：第 {p['lo']} 分钟起、到第 {p['hi']} 分钟之前，甲桩不供电。"
            "这期间挂在甲桩上的车电量不变，未满的半格也不累加、不清零。"
            "乙桩在这期间视为旁边没有车，按满功率计算，未满的半格清零。"
            "检修不推迟插枪，车可以挂在甲桩上干等。")


MODULES = {m.id: m for m in [
    Module("share", "并柜降功率", 10, _t_share),
    Module("block", "柜体检修", 15, _t_block),
    Module("topup", "补电", 20, _t_topup),
]}

METRICS = {
    "late": "总迟到分钟（各车充满时刻超出出发时刻的部分之和，提前充满记 0）",
    "late_n": "迟到车辆数",
}

OBJECTIVE_PHRASES = {
    "late": "总迟到分钟最小",
    "late_n": "迟到车辆数最小",
}


def _no_topup(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("topup", None)
    return x


def _block_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    block = x["modules"]["block"]
    x["modules"]["block"] = {**block, "hi": block["alt_hi"]}
    return x


COUNTERFACTUALS = {
    "no_topup": Counterfactual(_no_topup, lambda _w: "若取消补电、电量单位恢复为表中数值，"),
    "block_shift": Counterfactual(
        _block_shift,
        lambda w: f"若甲桩检修改为到第 {w['modules']['block']['alt_hi']} 分钟之前（其余不变），",
    ),
}

READINGS: dict = {}


def _simulate(starts: list[int], chargers: list[int], needs: list[int], share: bool,
              block: tuple[int, int] | None = None) -> list[int]:
    return dual_progress(starts, chargers, needs, share, block)


def greedy_depart(world: dict) -> tuple:
    cars = world["data"]["cars"]
    return tuple(c["id"] for c in sorted(cars, key=lambda c: (c["depart"], c["id"])))


def greedy_need(world: dict) -> tuple:
    cars = world["data"]["cars"]
    return tuple(c["id"] for c in sorted(cars, key=lambda c: (c["need"], c["id"])))


class ChargeFamily:
    id = "charge"
    primary = "late"
    shared = "late_n"
    cf_key = "no_topup"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_depart(w), greedy_need(w)])

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
        share = "share" in world["modules"]
        extra = world["modules"]["topup"]["extra"] if "topup" in world["modules"] else 0
        window = world["modules"].get("block")
        block = (window["lo"], window["hi"]) if window else None
        starts: list[int] = []
        chargers: list[int] = []
        needs: list[int] = []
        fired: set[str] = set()
        free = [0, 0]
        for pid in plan:
            car = cars[pid]
            b = 0 if free[0] <= free[1] else 1
            starts.append(free[b])
            chargers.append(b)
            needs.append(car["need"] + extra)
            done = _simulate(starts, chargers, needs, share, block)
            if block and any(chargers[i] == 0 and starts[i] < block[1] and done[i] > block[0] for i in range(len(starts))):
                fired.add("block")
            if share and any(done[i] > starts[i] + needs[i] for i in range(len(starts))):
                fired.add("share")
            free = [0, 0]
            for i, end in enumerate(done):
                free[chargers[i]] = max(free[chargers[i]], end)
        late = late_n = 0
        for pid, end in zip(plan, done):
            over = end - cars[pid]["depart"]
            if over > 0:
                late += over
                late_n += 1
        if extra:
            fired.add("topup")
        return Outcome(tuple(plan), {"late": late, "late_n": late_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        rows = [[c["id"], c["need"], c["depart"]] for c in world["data"]["cars"]]
        return "\n".join([
            "你给回场的营运车辆排插枪顺序。两根桩从 0 分钟起空闲，甲桩和乙桩接在同一面柜子上。",
            f"车辆表每行 `[编号, 需要的电量单位, 出发分钟]`：{_c(rows)}。车辆 0 分钟已在场，可以立即插枪。",
            "每辆车插到当前更早空闲的桩上；两桩同时空闲时插甲桩。插枪时刻就是该桩空闲的时刻，充满后该桩立刻空出。",
            "满功率时，每 1 分钟获得 1 个电量单位。迟到分钟 = max(0, 充满时刻 − 出发分钟)。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "late", "points": 6,
             "text": "给出最优插枪顺序，车辆编号用短横线连接，例如 A-B-C-D-E-F。"},
            {"name": "late", "metric": "late", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_late", "metric": "late", "points": 5, "cf": "no_topup"},
        ]


FAMILY = ChargeFamily()
