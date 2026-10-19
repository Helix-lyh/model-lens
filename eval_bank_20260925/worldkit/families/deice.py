"""机场除冰排队：一处除冰坪、一条跑道，决定飞机除冰顺序。除冰过早会让除冰液在等到时隙前失效。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome
from eval_bank_20260925.worldkit.share import dual_progress

DECISIONS = ("选除冰顺序",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_sep(p, _w):
    return f"跑道间隔：一架飞机起飞后，下一架至少再过 {p['minutes']} 分钟才能起飞。"


def _t_fluid(p, _w):
    return (f"Ⅰ型除冰液：每架飞机的保持分钟在其基础值上加 {p['bonus']} 分钟。"
            "再除冰时保持分钟长度不变，从新的除冰完成时刻重新起算。")


def _t_flush(p, _w):
    return (f"换型冲洗：同一处坪上，后一架与刚离开的型号不同时，该坪要空等 {p['minutes']} 分钟才能再接。"
            "型号相同，或该坪还没接过飞机，除冰完成后立刻可以再接。冲洗不增加除冰分钟。")


def _t_pump(_p, _w):
    return ("双坪并泵：两处除冰坪都在喷液的每一分钟，两机都只累积半格，同一架累积满 2 分钟才完成 1 个除冰单位。"
            "某一分钟只有一坪在喷时，该机该分钟完成 1 个除冰单位，此前未满的半格清零。"
            "每架飞机挂到当前更早空出的坪；两坪同时空出时挂甲坪。")


MODULES = {m.id: m for m in [
    Module("sep", "跑道间隔", 10, _t_sep),
    Module("flush", "换型冲洗", 15, _t_flush),
    Module("fluid", "除冰液", 20, _t_fluid),
    Module("pump", "双坪并泵", 25, _t_pump),
]}

METRICS = {
    "delay": "总延误分钟（各机起飞时刻减其跑道时隙，再求和）",
    "redeice": "额外除冰次数",
}

OBJECTIVE_PHRASES = {
    "delay": "总延误分钟最小",
    "redeice": "额外除冰次数最小",
}


def _no_fluid(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("fluid", None)
    return x


def _flush_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    flush = x["modules"]["flush"]
    x["modules"]["flush"] = {**flush, "minutes": flush["alt"]}
    return x


COUNTERFACTUALS = {
    "no_fluid": Counterfactual(_no_fluid, lambda _w: "若改用保持时间更短的除冰液、不再加这几分钟，"),
    "flush_shift": Counterfactual(
        _flush_shift,
        lambda w: f"若换型冲洗改为 {w['modules']['flush']['alt']} 分钟（其余不变），",
    ),
}

READINGS: dict = {}


def _planes(world: dict) -> dict[str, dict]:
    return {p["id"]: p for p in world["data"]["planes"]}


def _hold(world: dict, plane: dict) -> int:
    bonus = world["modules"]["fluid"]["bonus"] if "fluid" in world["modules"] else 0
    return plane["hold"] + bonus


def _simulate_pump(world: dict, plan: tuple, planes: dict) -> Outcome | None:
    sep = world["modules"]["sep"]["minutes"] if "sep" in world["modules"] else 0
    flush = world["modules"]["flush"]["minutes"] if "flush" in world["modules"] else 0
    extra_deice: dict[str, int] = {}
    fired: set[str] = set()
    fired.add("pump")
    if "fluid" in world["modules"]:
        fired.add("fluid")
    delay = redeice = last = 0
    for _ in range(3):
        free = [0, 0]
        last_kind: list[str | None] = [None, None]
        starts: list[int] = []
        pads: list[int] = []
        needs: list[int] = []
        pids: list[str] = []
        done: list[int] = []
        for pid in plan:
            p = planes[pid]

            def avail(b: int, p=p) -> int:
                gap = flush if last_kind[b] not in (None, p.get("kind")) else 0
                return free[b] + gap

            b = 0 if avail(0) <= avail(1) else 1
            if last_kind[b] not in (None, p.get("kind")) and flush:
                fired.add("flush")
            start = max(avail(b), p["ready"])
            pids.append(pid)
            starts.append(start)
            pads.append(b)
            needs.append(p["deice"] + extra_deice.get(pid, 0))
            done = dual_progress(starts, pads, needs, True)
            free = [0, 0]
            last_kind = [None, None]
            for i, end in enumerate(done):
                free[pads[i]] = max(free[pads[i]], end)
                last_kind[pads[i]] = planes[pids[i]].get("kind")
        runway = 0
        delay = redeice = last = 0
        more: dict[str, int] = {}
        for i, pid in enumerate(plan):
            p = planes[pid]
            hold = _hold(world, p)
            takeoff = max(done[i], p["slot"], runway)
            if takeoff > done[i] + hold:
                if pid in extra_deice:
                    return None
                more[pid] = p["deice"]
                redeice += 1
            delay += takeoff - p["slot"]
            last = max(last, takeoff)
            runway = takeoff + sep
            if sep:
                fired.add("sep")
        if not more:
            return Outcome(tuple(plan), {"delay": delay, "redeice": redeice, "last": last}, [], frozenset(fired))
        extra_deice.update(more)
    return None


def greedy_ready(world: dict) -> tuple:
    planes = world["data"]["planes"]
    return tuple(p["id"] for p in sorted(planes, key=lambda p: (p["ready"], p["slot"], p["id"])))


def greedy_slot(world: dict) -> tuple:
    """先赶跑道时隙。不计型号切换。"""
    planes = world["data"]["planes"]
    return tuple(p["id"] for p in sorted(planes, key=lambda p: (p["slot"], p["ready"], p["id"])))


def greedy_batch(world: dict) -> tuple:
    """同一型号做完再换，组内仍按时隙。冲洗分钟会让人先这么排。"""
    planes = world["data"]["planes"]
    groups: dict[str, list] = {}
    for p in planes:
        groups.setdefault(p["kind"], []).append(p)
    ordered = []
    for kind in sorted(groups, key=lambda k: (min(p["slot"] for p in groups[k]), k)):
        ordered.extend(sorted(groups[kind], key=lambda p: (p["slot"], p["ready"], p["id"])))
    return tuple(p["id"] for p in ordered)


def _greedies(world: dict) -> list[tuple]:
    out = [greedy_ready(world)]
    if "flush" in world["modules"]:
        out.insert(0, greedy_batch(world))
    return out


class DeiceFamily:
    id = "deice"
    primary = "delay"
    shared = "redeice"
    cf_key = "no_fluid"
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
        ids = [p["id"] for p in world["data"]["planes"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        planes = _planes(world)
        if len(plan) != len(planes) or set(plan) != set(planes):
            return None
        if "pump" in world["modules"]:
            return _simulate_pump(world, plan, planes)
        sep = world["modules"]["sep"]["minutes"] if "sep" in world["modules"] else 0
        flush = world["modules"]["flush"]["minutes"] if "flush" in world["modules"] else 0
        pad = runway = 0
        delay = redeice = last = 0
        prev_kind = None
        fired: set[str] = set()
        if "fluid" in world["modules"]:
            fired.add("fluid")
        for pid in plan:
            p = planes[pid]
            hold = _hold(world, p)
            gap = flush if prev_kind is not None and prev_kind != p["kind"] else 0
            if gap:
                fired.add("flush")
            start = max(pad + gap, p["ready"])
            prev_kind = p.get("kind")
            finish = start + p["deice"]
            rounds = 1
            while True:
                takeoff = max(finish, p["slot"], runway)
                if takeoff <= finish + hold:
                    break
                rounds += 1
                if rounds > 2:
                    return None
                finish += p["deice"]
            if rounds > 1:
                redeice += rounds - 1
            delay += takeoff - p["slot"]
            last = max(last, takeoff)
            runway = takeoff + sep
            if sep:
                fired.add("sep")
            pad = finish
        return Outcome(tuple(plan), {"delay": delay, "redeice": redeice, "last": last}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        flushed = "flush" in world["modules"]
        if flushed:
            rows = [[p["id"], p["ready"], p["slot"], p["deice"], p["hold"], p["kind"]] for p in world["data"]["planes"]]
            table = f"飞机表每行 `[编号, 就绪分钟, 跑道时隙, 除冰分钟, 基础保持分钟, 型号]`：{_c(rows)}。"
        else:
            rows = [[p["id"], p["ready"], p["slot"], p["deice"], p["hold"]] for p in world["data"]["planes"]]
            table = f"飞机表每行 `[编号, 就绪分钟, 跑道时隙, 除冰分钟, 基础保持分钟]`：{_c(rows)}。"
        if "pump" in world["modules"]:
            lead = "你在冬季机场排两处除冰坪。每架飞机挂到当前更早空出的坪；两坪同时空出时挂甲坪。顺序自选。"
            start = "开始除冰取该坪空出时刻与该机就绪分钟的较晚者。除冰单位见并泵规则。"
        else:
            lead = "你在冬季机场排一处除冰坪。除冰坪同一时刻只能服务一架飞机，顺序自选。"
            start = "开始除冰取除冰坪空出时刻与该机就绪分钟的较晚者。除冰期间除冰坪不空出。"
        return "\n".join([
            lead,
            table,
            start,
            "起飞取除冰完成、该机跑道时隙、跑道可用 三者最晚。"
            "若起飞晚于除冰完成加上保持分钟，除冰液失效，飞机留在坪上立刻再除一次，然后按新的完成时刻重算起飞。"
            "第三次仍失效则该顺序不可行。",
            "不得在除冰坪主动等待后再开始除冰。起飞顺序与除冰顺序相同：后除冰的飞机不能抢在先除冰的飞机前面起飞。"
            "总延误是各机起飞时刻减跑道时隙之和。额外除冰次数是各机第二次除冰次数之和。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "delay", "points": 6,
             "text": "给出最优除冰顺序，飞机编号用短横线连接，例如 A-B-C-D-E-F。"},
            {"name": "delay", "metric": "delay", "points": 5},
            {"name": "redeice", "metric": "redeice", "points": 4},
            {"name": "cf_delay", "metric": "delay", "points": 5, "cf": "no_fluid"},
        ]


FAMILY = DeiceFamily()
