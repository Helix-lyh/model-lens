"""出行题族：家到公司，选交通工具与路线，离散路段分钟计程。"""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选交通工具", "选路")

TOOLS = ("walk", "bike", "bus")
ROUTES = ("direct", "detour")
TOOL_ZH = {"walk": "步行", "bike": "骑车", "bus": "公交"}
ROUTE_ZH = {"direct": "直达", "detour": "绕行"}


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_lights(p, w):
    return (f"路口红绿灯：周期 {p['cycle']} 分钟，每个周期前 {p['green']} 分钟为绿灯、其余为红灯；"
            "进入带灯路段的时刻若落在红灯段，须先等到该周期绿灯再通行。骑车与步行受红绿灯影响，公交路段不计。")


def _t_rain(_p, _w):
    return "下雨：骑车在各路段上的行驶分钟数×2；步行与公交路段分钟不变。"


def _t_bus_schedule(p, w):
    return (f"公交班次：各公交路线的站点发车时刻表（分钟）为 {_c(p['times'])}。"
            "到达站点后若当次车已开走，须等到时刻表中下一班发车再上车；时刻表里没有更晚的班次则该方案不可行。")


def _t_transfer(p, _w):
    return (f"换乘：相邻两段所用交通工具不同时，下一段开始前额外等待 {p['minutes']} 分钟；"
            "工具相同则两段直接衔接，不多等。")


MODULES = {m.id: m for m in [
    Module("lights", "路口红绿灯", 10, _t_lights),
    Module("rain", "下雨", 20, _t_rain),
    Module("bus_schedule", "公交班次", 30, _t_bus_schedule),
    Module("transfer", "换乘等待", 40, _t_transfer),
]}

METRICS = {
    "arrive": "到达时刻",
    "fare": "车费",
}

OBJECTIVE_PHRASES = {
    "arrive": "到达时刻最小",
    "fare": "车费最小",
}

def _no_rain(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("rain", None)
    return x


COUNTERFACTUALS = {
    "no_rain": Counterfactual(_no_rain, lambda _w: "若未下雨，"),
}

READINGS: dict = {}


def _light_wait(clock: int, cycle: int, green: int) -> int:
    phase = clock % cycle
    return 0 if phase < green else cycle - phase


def _walk_bike_minutes(mode: str, world: dict, legs: list, clock: int | None = None) -> tuple[int, set[str]]:
    m = world["modules"]
    rain = mode == "bike" and "rain" in m
    fired: set[str] = set()
    clock = world["data"]["start"] if clock is None else clock
    for leg in legs:
        mins = leg["min"]
        if rain:
            mins *= 2
            fired.add("rain")
        if leg.get("lights") and "lights" in m:
            w = _light_wait(clock, m["lights"]["cycle"], m["lights"]["green"])
            if w:
                fired.add("lights")
            clock += w
        clock += mins
    return clock, fired


def _bus_minutes(world: dict, access: int, ride: int, clock: int | None = None) -> tuple[int, set[str]]:
    m = world["modules"]
    fired: set[str] = set()
    clock = (world["data"]["start"] if clock is None else clock) + access
    if "bus_schedule" in m:
        fired.add("bus_schedule")
        times = m["bus_schedule"]["times"]
        depart = next(t for t in times if t >= clock)
        clock = depart + ride
    else:
        clock += ride
    return clock, fired


def _nominal(tool: str, segs) -> int:
    if tool == "bus":
        return segs["access"] + segs["ride"]
    return sum(x["min"] for x in segs)


def greedy_leg_plan(world: dict) -> tuple:
    """每段只看表上的行驶分钟，不计红灯、下雨、班次和换乘。"""
    plan = []
    for leg in world["data"]["legs"]:
        best = min(
            (( _nominal(tool, leg[tool][route]), tool, route) for tool in TOOLS for route in ROUTES)
        )
        plan.extend((best[1], best[2]))
    return tuple(plan)


def _simulate_legs(world: dict, plan: tuple) -> Outcome | None:
    legs = world["data"]["legs"]
    if len(plan) != 2 * len(legs):
        return None
    pairs = []
    for i in range(0, len(plan), 2):
        tool, route = plan[i], plan[i + 1]
        if tool not in TOOLS or route not in ROUTES:
            return None
        pairs.append((tool, route))
    clock = world["data"]["start"]
    fare = 0
    fired: set[str] = set()
    prev = None
    trace = []
    transfer = world["modules"].get("transfer")
    for (tool, route), leg in zip(pairs, legs):
        if prev is not None and tool != prev and transfer:
            clock += int(transfer["minutes"])
            fired.add("transfer")
        prev = tool
        segs = leg[tool][route]
        try:
            if tool == "bus":
                arrive, f = _bus_minutes(world, segs["access"], segs["ride"], clock)
            else:
                arrive, f = _walk_bike_minutes(tool, world, segs, clock)
        except StopIteration:
            return None
        fired |= f
        clock = arrive
        fare += world["data"]["fare"][tool]
        trace.append([tool, route, arrive])
    return Outcome(plan, {"arrive": clock, "fare": fare}, trace, frozenset(fired))


def _legs_header(d: dict) -> str:
    lines = [
        f"{d['start']} 分钟你在{d['from_name']}，要赶到{d['to_name']}。"
        f"路程分成 {len(d['legs'])} 段，必须按段序走完，不能跳段、不能调换段序。"
        "每一段都要单独做两个决定：选交通工具（步行、骑车、公交），再选路（直达或绕行）。"
        "上一段的到达时刻就是下一段的出发时刻，所以前一段的选择会改变后一段赶上哪一班车、红灯等不等。",
    ]
    for i, leg in enumerate(d["legs"], 1):
        rows = []
        for tool in TOOLS:
            for route in ROUTES:
                segs = leg[tool][route]
                if tool == "bus":
                    rows.append([TOOL_ZH[tool], ROUTE_ZH[route], segs["access"], segs["ride"]])
                else:
                    rows.append([TOOL_ZH[tool], ROUTE_ZH[route], [x["min"] for x in segs]])
        lines.append(
            f"第{i}段（{leg['name']}）分钟表每行 `[工具, 路线, …]`："
            "步行/骑车是各路段行驶分钟（按顺序走，标了灯的路段才看红绿灯）；"
            f"公交是 `[工具, 路线, 到站分钟, 乘车分钟]`，到站分钟从本段出发时刻起算。表：{_c(rows)}。"
        )
    fares = [[TOOL_ZH[k], v] for k, v in d["fare"].items()]
    lines.append(f"车费按每一段分别累加（同一工具走两段计两次）。各工具每段车费（元）`[工具, 元]`：{_c(fares)}。")
    return "\n".join(lines)


def greedy_all_bike(world: dict) -> tuple:
    n = len(world["data"]["legs"]) if "legs" in world["data"] else 1
    return tuple(x for _ in range(n) for x in ("bike", "direct"))


class TripFamily:
    id = "trip"
    primary = "arrive"
    shared = "fare"
    cf_key = "no_rain"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_leg_plan(w), greedy_all_bike(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(plan) % 2:
            return None
        out = []
        for i in range(0, len(plan), 2):
            tool, route = plan[i].lower(), plan[i + 1].lower()
            if tool not in TOOLS or route not in ROUTES:
                return None
            out.extend((tool, route))
        return tuple(out)

    def plans(self, world: dict) -> Iterator[tuple]:
        if "legs" in world["data"]:
            choices = [(t, r) for t in TOOLS for r in ROUTES]
            for combo in itertools.product(choices, repeat=len(world["data"]["legs"])):
                yield tuple(x for pair in combo for x in pair)
            return
        for tool in TOOLS:
            for route in ROUTES:
                yield (tool, route)

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        if "legs" in world["data"]:
            return _simulate_legs(world, plan)
        if len(plan) != 2:
            return None
        tool, route = plan
        if tool not in TOOLS or route not in ROUTES:
            return None
        data = world["data"]
        segs = data["segments"][tool][route]
        fired: set[str] = set()
        if tool == "bus":
            try:
                arrive, f = _bus_minutes(world, segs["access"], segs["ride"])
            except StopIteration:
                return None
            fired |= f
        else:
            arrive, f = _walk_bike_minutes(tool, world, segs)
            fired |= f
        fare = data["fare"][tool]
        return Outcome(plan, {"arrive": arrive, "fare": fare}, [[tool, route, arrive]], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        if "legs" in d:
            return _legs_header(d)
        rows = []
        for tool in TOOLS:
            for route in ROUTES:
                segs = d["segments"][tool][route]
                if tool == "bus":
                    rows.append([TOOL_ZH[tool], ROUTE_ZH[route], segs["access"], segs["ride"]])
                else:
                    rows.append([TOOL_ZH[tool], ROUTE_ZH[route], [x["min"] for x in segs]])
        fares = [[TOOL_ZH[k], v] for k, v in d["fare"].items()]
        return "\n".join([
            f"{d['start']} 分钟你在{d['from_name']}，需前往{d['to_name']}。"
            "先选一种交通工具（步行、骑车、公交），再在该工具下选一条路线（直达或绕行）。",
            "路线分钟表每行 `[工具, 路线, …]`：步行/骑车为各路段行驶分钟列表（按顺序走）；"
            f"公交为 `[工具, 路线, 到站分钟, 乘车分钟]`。表：{_c(rows)}。",
            f"各工具固定车费（元）每行 `[工具, 元]`：{_c(fares)}。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        if len(layers) == 1:
            return f"目标：使{layers[0]}。"
        s = f"目标：先使{layers[0]}"
        for p in layers[1:-1]:
            s += f"，在此前提下使{p}"
        return s + f"；若仍有多个顺序并列，取{layers[-1]}者。"


FAMILY = TripFamily()


def frozen_world() -> dict:
    """手算冻结局面：有雨时步行绕行 12 分钟最优；无雨时骑车两条路都是 10 分钟，并列取绕行。"""
    return {
        "family": "trip",
        "data": {
            "start": 0,
            "from_name": "家",
            "to_name": "公司",
            "segments": {
                "walk": {
                    "direct": [{"min": 8}, {"min": 5, "lights": True}],
                    "detour": [{"min": 12}],
                },
                "bike": {
                    "direct": [{"min": 4}, {"min": 6, "lights": True}],
                    "detour": [{"min": 10}],
                },
                "bus": {
                    "direct": {"access": 3, "ride": 8},
                    "detour": {"access": 2, "ride": 12},
                },
            },
            "fare": {"walk": 0, "bike": 2, "bus": 4},
        },
        "modules": {
            "lights": {"cycle": 10, "green": 6},
            "rain": {},
            "bus_schedule": {"times": [5, 15, 25]},
        },
        "objective": ["arrive", "fare"],
        "objective_conditions": {},
        "questions": [
            {"name": "plan", "type": "plan", "metric": "arrive", "points": 6,
             "text": "给出最优工具与路线，用英文短码连写（WALK/BIKE/BUS 与 DIRECT/DETOUR，如 BIKE-DIRECT）。"},
            {"name": "arrive", "metric": "arrive", "points": 5},
            {"name": "fare", "metric": "fare", "points": 4},
            {"name": "dry_arrive", "metric": "arrive", "points": 5, "cf": "no_rain"},
        ],
        "background": [],
    }


def extreme_world() -> dict:
    path = Path(__file__).resolve().parents[1] / "worlds" / "trip" / "extreme.json"
    return json.loads(path.read_text(encoding="utf-8"))
