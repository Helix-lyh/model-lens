"""机坪推出：两辆拖车，决定航班推出顺序。换区要空等，两车同时拖则半格。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome
from eval_bank_20260925.worldkit.share import dual_progress

DECISIONS = ("选推出顺序",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_share(_p, _w):
    return ("并车：两辆拖车都在作业的每一分钟，两架航班都只累积半格，同一架累积满 2 分钟才完成 1 个拖车单位。"
            "某一分钟只有一辆在作业时，该架该分钟完成 1 个单位，此前未满的半格清零。")


def _t_zone(p, _w):
    return (f"换区：同一辆拖车上，后一架的停机区与刚完成的不同时，该车要空等 {p['minutes']} 分钟才能再挂。"
            "停机区相同，或这辆车还没拖过，完成后立刻可以再挂。空等不计入拖车单位。")


def _t_wide(p, _w):
    return f"宽体：宽体航班的拖车单位在表中数值上再加 {p['extra']}。并车仍按加完之后的单位计算。"


MODULES = {m.id: m for m in [
    Module("share", "并车", 10, _t_share),
    Module("zone", "换区", 20, _t_zone),
    Module("wide", "宽体加时", 30, _t_wide),
]}

METRICS = {
    "flow": "总推出完成分钟（各机完成时刻之和）",
    "late_n": "完成时刻晚于计划离港的架数",
}

OBJECTIVE_PHRASES = {
    "flow": "总推出完成分钟最小",
    "late_n": "误点架数最小",
}


def _zone_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    z = x["modules"]["zone"]
    x["modules"]["zone"] = {**z, "minutes": z["alt"]}
    return x


COUNTERFACTUALS = {
    "zone_shift": Counterfactual(
        _zone_shift,
        lambda w: f"若换区空等改为 {w['modules']['zone']['alt']} 分钟（其余不变），",
    ),
}

READINGS: dict = {}


def _need(world: dict, flight: dict) -> int:
    extra = world["modules"]["wide"]["extra"] if "wide" in world["modules"] and flight.get("wide") else 0
    return flight["tow"] + extra


def _finish_map(world: dict, plan: tuple) -> tuple[dict[str, int], bool] | None:
    flights = {f["id"]: f for f in world["data"]["flights"]}
    if len(plan) != len(flights) or set(plan) != set(flights):
        return None
    gap = world["modules"]["zone"]["minutes"] if "zone" in world["modules"] else 0
    share = "share" in world["modules"]
    free = [0, 0]
    last_zone: list[str | None] = [None, None]
    starts: list[int] = []
    sides: list[int] = []
    needs: list[int] = []
    pids: list[str] = []
    done: list[int] = []
    used_zone = False
    for pid in plan:
        flight = flights[pid]

        def avail(b: int, flight=flight) -> int:
            extra = gap if gap and last_zone[b] not in (None, flight["zone"]) else 0
            return free[b] + extra

        b = 0 if avail(0) <= avail(1) else 1
        if gap and last_zone[b] not in (None, flight["zone"]):
            used_zone = True
        start = max(avail(b), flight.get("ready", 0))
        pids.append(pid)
        starts.append(start)
        sides.append(b)
        needs.append(_need(world, flight))
        done = dual_progress(starts, sides, needs, share) if share else [s + n for s, n in zip(starts, needs)]
        free = [0, 0]
        last_zone = [None, None]
        for i, end in enumerate(done):
            free[sides[i]] = max(free[sides[i]], end)
            last_zone[sides[i]] = flights[pids[i]]["zone"]
    return {pid: end for pid, end in zip(pids, done)}, used_zone


def greedy_dep(world: dict) -> tuple:
    return tuple(f["id"] for f in sorted(world["data"]["flights"], key=lambda f: (f["dep"], f["id"])))


def greedy_short(world: dict) -> tuple:
    return tuple(f["id"] for f in sorted(world["data"]["flights"], key=lambda f: (_need(world, f), f["id"])))


def greedy_zone(world: dict) -> tuple:
    return tuple(f["id"] for f in sorted(world["data"]["flights"], key=lambda f: (f["zone"], f["dep"], f["id"])))


class PushFamily:
    id = "push"
    primary = "flow"
    shared = "late_n"
    cf_key = "zone_shift"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_dep(w), greedy_short(w), greedy_zone(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 1 and "A" <= p <= "H" for p in plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [f["id"] for f in world["data"]["flights"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        mapped = _finish_map(world, plan)
        if mapped is None:
            return None
        finishes, used_zone = mapped
        flights = {f["id"]: f for f in world["data"]["flights"]}
        late_n = sum(1 for fid, end in finishes.items() if end > flights[fid]["dep"])
        fired: set[str] = set()
        if used_zone:
            fired.add("zone")
        if "share" in world["modules"]:
            fired.add("share")
        if "wide" in world["modules"] and any(f.get("wide") for f in flights.values()):
            fired.add("wide")
        return Outcome(tuple(plan), {"flow": sum(finishes.values()), "late_n": late_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        rows = [[f["id"], f["dep"], f["tow"], f["zone"], "宽体" if f.get("wide") else "窄体"]
                for f in world["data"]["flights"]]
        return "\n".join([
            "你排机坪推出。两辆拖车从 0 分钟起空闲，决定航班挂车的先后。",
            f"航班表每行 `[编号, 计划离港分钟, 拖车单位, 停机区, 机型]`：{_c(rows)}。航班 0 分钟都已到位。",
            "每架挂到「加上换区空等之后能更早开工」的那辆拖车；两车同时能开工时挂甲车。"
            "挂车时刻就是该车可以开工的时刻，不是上一单刚完成的时刻。",
            "答题记号：航班编号按推出先后用短横线连接，例如 A-B-C-D-E-F-G。每架恰好一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "flow", "points": 6,
             "text": "给出最优推出顺序，航班编号用短横线连接，例如 A-B-C-D-E-F-G。"},
            {"name": "flow", "metric": "flow", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_flow", "metric": "flow", "points": 5, "cf": "zone_shift"},
        ]


FAMILY = PushFamily()
