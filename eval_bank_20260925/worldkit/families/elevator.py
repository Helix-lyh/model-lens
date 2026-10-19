"""电梯题族：固定楼层、呼叫表与停靠点编号，自选停靠顺序；满员时按规则选单。"""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选单", "选顺序")


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_cap(p, _w):
    return f"轿厢上限 {p['max']} 人：某层开门上客时，若已有 {p['max']} 人在轿厢内则不得再上；本层其余等待者继续等下一趟。"


def _t_door(p, _w):
    return f"每次停靠（无论是否有人上下）开门、上下客、关门合计 {p['minutes']} 分钟。"


def _t_peak(p, _w):
    return (f"禁停：{p['from_t']} 分钟至 {p['to_t']} 分钟（含起点、不含终点）内，"
            f"电梯到达 {p['floor']} 层后不得开门，须等到 {p['to_t']} 分钟才能开门。"
            "禁停只推迟这一次开门，不取消这次停靠，也不改变你写下的停靠顺序。")


MODULES = {m.id: m for m in [
    Module("cap", "轿厢上限", 10, _t_cap),
    Module("door", "开关门耗时", 20, _t_door),
    Module("peak", "禁停时段", 30, _t_peak),
]}

METRICS = {
    "total_wait": "总等待（各乘客送达时刻减其出现时刻，再求和）",
    "max_wait": "最长单人等待",
}

OBJECTIVE_PHRASES = {
    "total_wait": "总等待最小",
    "max_wait": "最长单人等待最小",
}


def _cap_plus_one(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"]["cap"]["max"] += 1
    return x


COUNTERFACTUALS = {
    "cap_plus_one": Counterfactual(
        _cap_plus_one,
        lambda _w: "若轿厢上限加 1（其余不变），",
    ),
}

READINGS: dict = {}


def _calls(world: dict) -> list[tuple[str, int, int, int]]:
    out = []
    for row in world["data"]["calls"]:
        out.append((row["id"], row["from"], row["to"], row["at"]))
    return out


def greedy_call_order(world: dict) -> tuple:
    """停靠点按编号。必须覆盖全部停靠，否则模拟会送不完人。"""
    stops = world["data"]["stops"]
    if isinstance(stops, dict):
        return tuple(sorted(stops))
    return tuple(stops)


class ElevatorFamily:
    id = "elevator"
    primary = "total_wait"
    shared = "max_wait"
    cf_key = "cap_plus_one"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_call_order(w)])

    def effective(self, world: dict) -> dict:
        return world

    def active_orders(self, world: dict) -> list[str]:
        return sorted(world["data"]["stops"])

    def plans(self, world: dict) -> Iterator[tuple]:
        stops = world["data"]["stops"]
        for perm in itertools.permutations(stops):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        data, m = world["data"], world["modules"]
        stops = data["stops"]
        if set(plan) != set(stops) or len(plan) != len(stops):
            return None
        speed = data.get("speed", 1)
        calls = _calls(world)
        cap = m["cap"]["max"] if "cap" in m else len(calls) + 1
        door = m["door"]["minutes"] if "door" in m else 0
        peak = m.get("peak")
        floor = data["start_floor"]
        clock = data["start_time"]
        onboard: list[tuple[str, int, int]] = []
        picked: set[str] = set()
        delivered: dict[str, int] = {}
        fired: set[str] = set()

        def waiting_at(f: int) -> list[tuple[str, int, int, int]]:
            rows = [
                c for c in calls
                if c[0] not in picked and c[0] not in delivered and c[1] == f and c[3] <= clock
            ]
            return sorted(rows, key=lambda c: (c[3], c[0]))

        trace: list = []
        for tok in plan:
            target = stops[tok]
            if target != floor:
                clock += abs(target - floor) * speed
                floor = target
            if peak and floor == peak["floor"] and peak["from_t"] <= clock < peak["to_t"]:
                clock = peak["to_t"]
                fired.add("peak")
            clock += door
            fired.add("door")
            still = []
            for pid, dest, ap in onboard:
                if dest == floor:
                    delivered[pid] = clock
                else:
                    still.append((pid, dest, ap))
            onboard = still
            for c in waiting_at(floor):
                if len(onboard) >= cap:
                    fired.add("cap")
                    break
                pid, _fr, to, ap = c
                onboard.append((pid, to, ap))
                picked.add(pid)
            trace.append([tok, floor, clock, sorted(p[0] for p in onboard), dict(delivered)])

        if len(delivered) != len(calls):
            return None
        waits = {c[0]: delivered[c[0]] - c[3] for c in calls}
        metrics = {"total_wait": sum(waits.values()), "max_wait": max(waits.values())}
        return Outcome(plan, metrics, trace, frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        calls = [[c["id"], c["from"], c["to"], c["at"]] for c in d["calls"]]
        stop_rows = [[k, v] for k, v in sorted(d["stops"].items())]
        return "\n".join([
            f"一部 {d['floors']} 层电梯，{d['start_time']} 分钟在 {d['start_floor']} 层。"
            f"相邻层之间运行 {d.get('speed', 1)} 分钟/层。",
            f"呼叫表每行 `[编号, 出现层, 目的层, 出现时刻(分钟)]`：{_c(calls)}。"
            "乘客在出现时刻起在该层等待，直至被送达目的层；等待 = 送达时刻 − 出现时刻。",
            f"停靠点表每行 `[编号, 层]`（各点恰好停靠一次，顺序自选；编号仅用于答题）：{_c(stop_rows)}。",
            "每次停靠：先下后上。"
            f"选单：上客时若已达轿厢上限，按出现时刻先后、同时刻按呼叫编号依次尝试登梯，满员则其余继续等待。"
            "选顺序：你安排上表停靠点编号的执行顺序。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        if len(layers) == 1:
            return f"目标：使{layers[0]}。"
        s = f"目标：先使{layers[0]}"
        for p in layers[1:-1]:
            s += f"，在此前提下使{p}"
        return s + f"；若仍有多个顺序并列，取{layers[-1]}者。"


FAMILY = ElevatorFamily()


def frozen_world() -> dict:
    """4 层、5 次停靠、cap=2：最优须先 3 层而非「谁近先接」的 2 层；cap+1 时总等待更小。"""
    return {
        "family": "elevator",
        "data": {
            "floors": 4,
            "start_floor": 1,
            "start_time": 0,
            "speed": 1,
            "calls": [
                {"id": "P1", "from": 2, "to": 4, "at": 0},
                {"id": "P2", "from": 3, "to": 1, "at": 0},
                {"id": "P3", "from": 1, "to": 3, "at": 5},
                {"id": "P4", "from": 1, "to": 4, "at": 6},
            ],
            "stops": {"A": 3, "B": 1, "C": 3, "D": 2, "E": 4},
        },
        "modules": {
            "cap": {"max": 2},
            "door": {"minutes": 2},
        },
        "objective": ["total_wait", "max_wait"],
        "objective_conditions": {},
        "questions": [
            {"name": "plan", "type": "plan", "metric": "total_wait", "points": 6,
             "text": "给出最优停靠点编号顺序，用短横线连接（如 A-B-C-D-E）。"},
            {"name": "total_wait", "metric": "total_wait", "points": 5},
            {"name": "max_wait", "metric": "max_wait", "points": 5},
            {"name": "cf_total_wait", "metric": "total_wait", "points": 4, "cf": "cap_plus_one"},
        ],
        "background": [],
    }


def high_then_return_plan(world: dict) -> tuple:
    """先在起点层上车，先去最高层，立刻回起点放下行的人，其余停靠按楼层从高到低。"""
    stops = world["data"]["stops"]
    start = world["data"]["start_floor"]
    lobby = sorted(k for k, f in stops.items() if f == start)
    first, last_lobby = lobby[0], lobby[-1]
    rest = [k for k in stops if k not in lobby]
    highest = max(rest, key=lambda k: (stops[k], k))
    tail = sorted((k for k in rest if k != highest), key=lambda k: (-stops[k], k))
    return (first, highest, last_lobby, *tail)


def nearest_stop_plan(world: dict) -> tuple:
    """从当前层反复去最近的未停靠点；距离相同取编号更小者。不计禁停和满员。"""
    stops = world["data"]["stops"]
    floor = world["data"]["start_floor"]
    left = set(stops)
    plan = []
    while left:
        tok = min(left, key=lambda k: (abs(stops[k] - floor), k))
        plan.append(tok)
        floor = stops[tok]
        left.remove(tok)
    return tuple(plan)


def extreme_world() -> dict:
    path = Path(__file__).resolve().parents[1] / "worlds" / "elevator" / "extreme.json"
    return json.loads(path.read_text(encoding="utf-8"))
