"""路口时段：车流股数已定。每股只选时段和绿灯档。同一时段绿灯取最长档，不累加。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选时段", "选绿灯档")
GREENS = ("S", "L")


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_share(_p, _w):
    return ("共用绿灯：分到同一时段的多股车流共用这一时段的绿灯。"
            "绿灯秒数取这些股所选档位里最长的一档，各股的绿灯秒数不累加。")


def _t_offset(p, _w):
    return (f"干线协调：编号 {p['phase']} 那一股所选时段的开始时刻必须落在 [{p['lo']}, {p['hi']}) 秒内"
            "（含起点、不含终点），否则冲掉上游绿波，该方案不可行。")


def _t_rain(p, _w):
    return f"雨天：车头时距在基础值上增加 {p['extra']} 秒。"


MODULES = {m.id: m for m in [
    Module("share", "共用绿灯", 10, _t_share),
    Module("offset", "干线协调", 20, _t_offset),
    Module("rain", "雨天", 30, _t_rain),
]}

METRICS = {
    "delay": "总延误秒数",
    "wait_n": "本时段未放完的车辆数",
}

OBJECTIVE_PHRASES = {
    "delay": "总延误秒数最小",
    "wait_n": "未放完车辆数最小",
}


def _offset_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    off = x["modules"]["offset"]
    x["modules"]["offset"] = {**off, "lo": off["alt_lo"], "hi": off["alt_hi"]}
    return x


COUNTERFACTUALS = {
    "offset_shift": Counterfactual(
        _offset_shift,
        lambda w: f"若干线协调窗口改为 [{w['modules']['offset']['alt_lo']}, {w['modules']['offset']['alt_hi']}) 秒（其余不变），",
    ),
}

READINGS: dict = {}


def _parse(plan: tuple, streams: dict, n_slots: int) -> list[tuple[str, int, str]] | None:
    if len(plan) != len(streams):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 3 or tok[0] not in streams:
            return None
        if tok[0] in seen:
            return None
        if not tok[1].isdigit() or not (1 <= int(tok[1]) <= n_slots):
            return None
        if tok[2] not in GREENS:
            return None
        seen.add(tok[0])
        out.append((tok[0], int(tok[1]) - 1, tok[2]))
    if seen != set(streams):
        return None
    return out


def _headway(world: dict) -> int:
    h = world["data"]["headway"]
    rain = world["modules"].get("rain")
    return h + (rain["extra"] if rain else 0)


def greedy_count(world: dict) -> tuple:
    """车多的股先占开始更早、绿灯更长的时段。"""
    streams = world["data"]["streams"]
    n_slots = world["data"]["n_slots"]
    off = world["modules"].get("offset")
    starts = world["data"]["slot_start"]
    order = sorted(streams, key=lambda s: (-s["n"], s["id"]))
    used = [0] * n_slots
    plan_map: dict[str, str] = {}
    for s in order:
        slots = range(n_slots)
        if off and s["id"] == off["phase"]:
            slots = [i for i in slots if off["lo"] <= starts[i] < off["hi"]] or list(range(n_slots))
        slot = min(slots, key=lambda i: (used[i], i))
        g = "L" if s["n"] >= 4 else "S"
        used[slot] += s["n"]
        plan_map[s["id"]] = s["id"] + str(slot + 1) + g
    return tuple(plan_map[s["id"]] for s in streams)


class CycleFamily:
    id = "cycle"
    primary = "delay"
    shared = "wait_n"
    cf_key = "offset_shift"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_count(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 3 and "A" <= p[0] <= "H" and p[1] in "12345" and p[2] in "SL" for p in plan):
            return None
        if len({p[0] for p in plan}) != len(plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [s["id"] for s in world["data"]["streams"]]
        n_slots = world["data"]["n_slots"]
        choices = [str(w) + g for w in range(1, n_slots + 1) for g in GREENS]
        for assign in itertools.product(choices, repeat=len(ids)):
            yield tuple(s + c for s, c in zip(ids, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        streams = {s["id"]: s for s in world["data"]["streams"]}
        n_slots = world["data"]["n_slots"]
        parsed = _parse(plan, streams, n_slots)
        if parsed is None:
            return None
        starts = world["data"]["slot_start"]
        gsec = world["data"]["greens"]
        off = world["modules"].get("offset")
        share = "share" in world["modules"]
        fired: set[str] = set()
        by_slot: list[list[tuple[str, str]]] = [[] for _ in range(n_slots)]
        for sid, w, g in parsed:
            if off and sid == off["phase"] and not (off["lo"] <= starts[w] < off["hi"]):
                return None
            if off and sid == off["phase"]:
                fired.add("offset")
            by_slot[w].append((sid, g))
        headway = _headway(world)
        if "rain" in world["modules"]:
            fired.add("rain")
        miss = world["data"]["miss"]
        delay = wait_n = 0
        for w, group in enumerate(by_slot):
            if not group:
                continue
            secs = [gsec[g] for _sid, g in group]
            green = max(secs) if share else sum(secs)
            if share:
                fired.add("share")
            cap = green // headway
            load = sum(streams[sid]["n"] for sid, _g in group)
            excess = max(0, load - cap)
            wait_n += excess
            delay += excess * miss + load * starts[w]
        return Outcome(tuple(plan), {"delay": delay, "wait_n": wait_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        rows = [[s["id"], s["name"], s["n"]] for s in d["streams"]]
        starts = [[i + 1, t] for i, t in enumerate(d["slot_start"])]
        return "\n".join([
            "你在为一个路口排本周期的时段。车流股数已定，只决定每一股放进哪一时段、用短绿灯还是长绿灯。",
            f"车流表每行 `[编号, 方向, 辆数]`：{_c(rows)}。股的先后固定，不能改编号顺序。",
            f"时段开始时刻每行 `[时段, 秒]`：{_c(starts)}。短绿灯 {d['greens']['S']} 秒，长绿灯 {d['greens']['L']} 秒。",
            f"车头时距 {d['headway']} 秒：一个时段里只按完整间隔放行，放不下的车每辆计 {d['miss']} 秒延误。"
            "放进某一时段的全部车辆还要计入该时段开始时刻那么多秒的等待。",
            "答题记号：每股写「编号+时段+档」，S 短 L 长，按车流表顺序用短横线连接，例如 A1L-B2S。每股恰好一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个方案并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "delay", "points": 6,
             "text": "给出最优方案，记号如 A1L-B2S-C1S。"},
            {"name": "delay", "metric": "delay", "points": 5},
            {"name": "wait_n", "metric": "wait_n", "points": 4},
            {"name": "cf_delay", "metric": "delay", "points": 5, "cf": "offset_shift"},
        ]


FAMILY = CycleFamily()
