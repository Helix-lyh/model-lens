"""十字路口信号配时：一个周期内排相位顺序，并为每个相位选短绿灯或长绿灯。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

PHASES = ("NS", "EW", "NL", "EL")
PHASE_ZH = {"NS": "南北直行", "EW": "东西直行", "NL": "南北左转", "EL": "东西左转", "PD": "行人专用"}
KNOWN = PHASES + ("PD",)
DECISIONS = ("选相位顺序", "选绿灯长短")


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _green_line(greens: dict) -> str:
    names = {"S": "短", "M": "中", "L": "长"}
    parts = [f"{names.get(k, k)}绿灯 {greens[k]} 秒" for k in ("S", "M", "L") if k in greens]
    return "、".join(parts) + "。"


def _t_ped(p, _w):
    return (f"人行横道：{PHASE_ZH[p['phase']]}相位的绿灯短于 {p['min']} 秒时，"
            "行人过不完，该方案不可行。")


def _t_offset(p, _w):
    return (f"干线协调：南北直行的绿灯开始时刻必须落在 [{p['lo']}, {p['hi']}) 秒内"
            "（含起点、不含终点），否则冲掉上游绿波，该方案不可行。")


def _t_rain(p, _w):
    return f"雨天：路面打滑，车头时距在基础值上增加 {p['extra']} 秒。未通过的车辆不加这项。"


MODULES = {m.id: m for m in [
    Module("ped", "人行横道", 10, _t_ped),
    Module("offset", "干线协调", 20, _t_offset),
    Module("rain", "雨天", 30, _t_rain),
]}

METRICS = {
    "delay": "总延误秒数",
    "max_delay": "单车最大延误秒数",
    "wait_n": "需要等待或本周期未通过的车辆数",
}

OBJECTIVE_PHRASES = {
    "delay": "总延误秒数最小",
    "max_delay": "单车最大延误秒数最小",
}


def _no_rain(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("rain", None)
    return x


def _offset_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    off = x["modules"]["offset"]
    x["modules"]["offset"] = {**off, "lo": off["alt_lo"], "hi": off["alt_hi"]}
    return x


COUNTERFACTUALS = {
    "no_rain": Counterfactual(_no_rain, lambda _w: "若未下雨、车头时距恢复基础值，"),
    "offset_shift": Counterfactual(
        _offset_shift,
        lambda w: (
            f"若干线协调窗口改为 [{w['modules']['offset']['alt_lo']}, {w['modules']['offset']['alt_hi']}) 秒"
            "（含起点、不含终点），"
        ),
    ),
}

READINGS: dict = {}


def _vehicles(data: dict) -> list[tuple[str, int]]:
    out = []
    for row in data["vehicles"]:
        for _ in range(row["n"]):
            out.append((row["phase"], row["at"]))
    return out


def _phases(data: dict) -> tuple[str, ...]:
    return tuple(data.get("phases", PHASES))


def _gcodes(data: dict) -> tuple[str, ...]:
    return tuple(k for k in "SML" if k in data["greens"])


def _parse(plan: tuple, phases: tuple[str, ...], gcodes: tuple[str, ...]) -> list[tuple[str, str]] | None:
    if len(plan) != len(phases):
        return None
    out = []
    for tok in plan:
        if len(tok) != 3 or tok[:2] not in phases or tok[2] not in gcodes:
            return None
        out.append((tok[:2], tok[2]))
    if len({p for p, _ in out}) != len(phases):
        return None
    return out


def _headway(world: dict) -> int:
    extra = world["modules"]["rain"]["extra"] if "rain" in world["modules"] else 0
    return world["data"]["headway"] + extra


def _serve(world: dict, plan: tuple) -> tuple[dict[str, int], set[str]] | None:
    data = world["data"]
    parsed = _parse(plan, _phases(data), _gcodes(data))
    if parsed is None:
        return None
    vehs = _vehicles(data)
    served = [False] * len(vehs)
    delay = max_delay = wait_n = 0
    clock = 0
    fired: set[str] = set()
    headway = _headway(world)
    mods = world["modules"]
    ped, offset = mods.get("ped"), mods.get("offset")
    for phase, gcode in parsed:
        start = clock + data["lost"]
        green = data["greens"][gcode]
        end = start + green
        if offset and phase == "NS":
            if not (offset["lo"] <= start < offset["hi"]):
                return None
            fired.add("offset")
        if ped and phase == ped["phase"] and green < ped["min"]:
            return None
        if ped and phase == ped["phase"]:
            fired.add("ped")
        last = None
        for i, (ph, at) in enumerate(vehs):
            if served[i] or ph != phase:
                continue
            leave = at if last is None else max(at, last + headway)
            leave = max(leave, start)
            if leave < end:
                served[i] = True
                last = leave
                d = leave - at
                delay += d
                max_delay = max(max_delay, d)
                if d:
                    wait_n += 1
        clock = end
    if "rain" in mods:
        fired.add("rain")
    miss = data["miss"]
    for i in range(len(vehs)):
        if not served[i]:
            delay += miss
            max_delay = max(max_delay, miss)
            wait_n += 1
    return {"delay": delay, "max_delay": max_delay, "wait_n": wait_n}, fired


def _phase_ok(world: dict, phase: str, gcode: str, clock: int, served: list[bool]) -> bool:
    """这个绿灯能不能让该相位在当前时刻开始后、本相位的车全部通过。"""
    data = world["data"]
    ped = world["modules"].get("ped")
    if ped and phase == ped["phase"] and data["greens"][gcode] < ped["min"]:
        return False
    start = clock + data["lost"]
    offset = world["modules"].get("offset")
    if offset and phase == "NS" and not (offset["lo"] <= start < offset["hi"]):
        return False
    end = start + data["greens"][gcode]
    headway = _headway(world)
    last = None
    for i, (ph, at) in enumerate(_vehicles(data)):
        if served[i] or ph != phase:
            continue
        leave = at if last is None else max(at, last + headway)
        leave = max(leave, start)
        if leave >= end:
            return False
        last = leave
    return True


def _hard_ok(world: dict, phase: str, gcode: str, clock: int) -> bool:
    data = world["data"]
    ped = world["modules"].get("ped")
    if ped and phase == ped["phase"] and data["greens"][gcode] < ped["min"]:
        return False
    start = clock + data["lost"]
    offset = world["modules"].get("offset")
    if offset and phase == "NS" and not (offset["lo"] <= start < offset["hi"]):
        return False
    return True


def _greedy(world: dict, order: tuple[str, ...]) -> tuple | None:
    served = [False] * len(_vehicles(world["data"]))
    clock = 0
    plan = []
    gcodes = sorted(_gcodes(world["data"]), key=lambda g: world["data"]["greens"][g])
    for phase in order:
        chosen = None
        for gcode in gcodes:
            if _phase_ok(world, phase, gcode, clock, served):
                chosen = gcode
                break
        if chosen is None:
            for gcode in reversed(gcodes):
                if _hard_ok(world, phase, gcode, clock):
                    chosen = gcode
                    break
        if chosen is None:
            return None
        served, clock = _advance(world, served, clock, phase, chosen)
        if served is None:
            return None
        plan.append(phase + chosen)
    return tuple(plan)


def _advance(world, served, clock, phase, gcode):
    data = world["data"]
    start = clock + data["lost"]
    end = start + data["greens"][gcode]
    offset = world["modules"].get("offset")
    ped = world["modules"].get("ped")
    if offset and phase == "NS" and not (offset["lo"] <= start < offset["hi"]):
        return None, clock
    if ped and phase == ped["phase"] and data["greens"][gcode] < ped["min"]:
        return None, clock
    headway = _headway(world)
    last = None
    served = list(served)
    vehs = _vehicles(data)
    for i, (ph, at) in enumerate(vehs):
        if served[i] or ph != phase:
            continue
        leave = at if last is None else max(at, last + headway)
        leave = max(leave, start)
        if leave < end:
            served[i] = True
            last = leave
    return served, end


def greedy_count(world: dict) -> tuple | None:
    """车多的相位先放，并尽量用更短的绿灯清空。"""
    phases = _phases(world["data"])
    counts: dict[str, int] = {p: 0 for p in phases}
    for ph, _at in _vehicles(world["data"]):
        counts[ph] += 1
    order = tuple(sorted(phases, key=lambda p: (-counts[p], p)))
    return _greedy(world, order)


def greedy_earliest(world: dict) -> tuple | None:
    """先放最早有车到达的相位，并尽量用更短的绿灯清空。"""
    phases = _phases(world["data"])
    first = {p: 10**9 for p in phases}
    for ph, at in _vehicles(world["data"]):
        first[ph] = min(first[ph], at)
    order = tuple(sorted(phases, key=lambda p: (first[p], p)))
    return _greedy(world, order)


class SignalFamily:
    id = "signal"
    primary = "delay"
    shared = "wait_n"
    cf_key = "no_rain"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_count(w), greedy_earliest(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 4 or len(plan) > 6:
            return None
        out = []
        for tok in plan:
            if len(tok) != 3 or tok[:2] not in KNOWN or tok[2] not in "SML":
                return None
            out.append(tok[:2])
        if len(set(out)) != len(out):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        phases, gcodes = _phases(world["data"]), _gcodes(world["data"])
        for perm in itertools.permutations(phases):
            for greens in itertools.product(gcodes, repeat=len(phases)):
                yield tuple(p + g for p, g in zip(perm, greens))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        got = _serve(world, plan)
        if got is None:
            return None
        metrics, fired = got
        return Outcome(tuple(plan), metrics, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        rows = [[PHASE_ZH[r["phase"]], r["at"], r["n"]] for r in d["vehicles"]]
        return "\n".join([
            f"你在为一座十字路口排这一个周期的信号。{len(_phases(d))} 个相位都要放行恰好一次，不能并行。",
            "选相位顺序，再为每个相位选绿灯档。",
            _green_line(d["greens"])
            + f"每个相位开始前有 {d['lost']} 秒全红，全红不放行。时钟从 0 秒起算。",
            f"车辆表每行 `[相位, 到达秒, 辆数]`：{_c(rows)}。同一到达秒的多辆车按表中顺序依次通过。",
            f"车头时距 {d['headway']} 秒：同一相位相邻两车的通过时刻至少相隔这么多秒。"
            "一辆车必须已经到达、绿灯已经开始、且与同相位前车至少隔一个车头时距，三者里最晚的那个时刻通过；"
            "通过时刻必须严格早于该相位绿灯结束。",
            f"本周期没通过的车，每辆计 {d['miss']} 秒延误（留给下一周期），并计入等待车辆。通过时刻晚于到达秒的车也计入等待车辆，延误 = 通过秒 − 到达秒。",
            "相位记号由缩写加一位组成：S 短、M 中、L 长。"
            "缩写 NS 南北直行、EW 东西直行、NL 南北左转、EL 东西左转、PD 行人专用。"
            "只使用车辆表里出现的相位，每个相位恰好一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        s = f"目标：先使{layers[0]}"
        return s + f"；若仍有多个方案并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "delay", "points": 6,
             "text": "给出最优相位方案。每个相位一个三字母记号，用短横线连接，例如 NSS-EWL-NLS-ELL；有行人专用相位时用 PDS 或 PDL。"},
            {"name": "delay", "metric": "delay", "points": 5},
            {"name": "wait_n", "metric": "wait_n", "points": 4},
            {"name": "cf_delay", "metric": "delay", "points": 5, "cf": "no_rain"},
        ]


FAMILY = SignalFamily()
