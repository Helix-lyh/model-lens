"""港口堆场：船期和靠泊已定。每艘船只选箱区和集卡波次。超员整船往下波挤，箱位过线整船降速。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选箱区", "选集卡波次")


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_wave(p, _w):
    return (f"波次容量：每一波集卡最多拉 {p['cap']} 个箱位。一艘船的箱子从它选定的那一波起装，"
            "这一波装不下的整段余量挤到后面的波次，直到装完。"
            "完成波次是最后装上余量的那一波。后面再也装不下则该方案不可行。")


def _t_yard(p, _w):
    return (f"箱位降速：某艘船开始进场时，若它选的箱区已有箱量达到 {p['thresh']} 或更多，"
            f"这艘船的完成时刻在完成波次时刻上再加 {p['slow']} 分钟。差一箱也是整船加，不按比例。"
            "进场后箱量才累加。不同箱区互不影响。")


MODULES = {m.id: m for m in [
    Module("wave", "波次容量", 10, _t_wave),
    Module("yard", "箱位降速", 20, _t_yard),
]}

METRICS = {
    "over": "过潮分钟之和（各船完成时刻超出潮汐时限的部分之和，未超出记 0）",
    "late_n": "过潮船数",
}

OBJECTIVE_PHRASES = {
    "over": "过潮分钟之和最小",
    "late_n": "过潮船数最小",
}


def _thresh_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    y = x["modules"]["yard"]
    x["modules"]["yard"] = {**y, "thresh": y["alt"]}
    return x


COUNTERFACTUALS = {
    "thresh_shift": Counterfactual(
        _thresh_shift,
        lambda w: f"若箱位降速门槛改为 {w['modules']['yard']['alt']}（其余不变），",
    ),
}

READINGS: dict = {}


def _parse(plan: tuple, ships: dict, yards: set[str], n_waves: int) -> list[tuple[str, int, str]] | None:
    if len(plan) != len(ships):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 3 or tok[0] not in ships:
            return None
        if tok[0] in seen:
            return None
        if not tok[1].isdigit() or not (1 <= int(tok[1]) <= n_waves):
            return None
        if tok[2] not in yards:
            return None
        seen.add(tok[0])
        out.append((tok[0], int(tok[1]) - 1, tok[2]))
    if seen != set(ships):
        return None
    return out


def _place(used: list[int], start: int, boxes: int, cap: int) -> tuple[list[int], int] | None:
    remaining = boxes
    last = start
    nxt = list(used)
    for w in range(start, len(nxt)):
        room = cap - nxt[w]
        if room <= 0:
            continue
        take = min(remaining, room)
        nxt[w] += take
        remaining -= take
        last = w
        if remaining == 0:
            return nxt, last
    return None


def greedy_earliest(world: dict) -> tuple:
    """每艘船单独看：能一次装进的最早波次，箱量更少的箱区。"""
    ships = world["data"]["ships"]
    yards = [y["id"] for y in world["data"]["yards"]]
    cap = world["modules"]["wave"]["cap"]
    n_waves = world["data"]["n_waves"]
    used = [0] * n_waves
    stock = {y: 0 for y in yards}
    plan = []
    for ship in ships:
        chosen = None
        for w in range(n_waves):
            room = cap - used[w]
            if room < ship["boxes"]:
                continue
            yard = min(yards, key=lambda y: (stock[y], y))
            chosen = (w, yard)
            break
        if chosen is None:
            w = n_waves - 1
            yard = min(yards, key=lambda y: (stock[y], y))
            chosen = (w, yard)
        w, yard = chosen
        placed = _place(used, w, ship["boxes"], cap)
        if placed:
            used, _ = placed
        stock[yard] += ship["boxes"]
        plan.append(ship["id"] + str(w + 1) + yard)
    return tuple(plan)


class YardFamily:
    id = "yard"
    primary = "over"
    shared = "late_n"
    cf_key = "thresh_shift"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_earliest(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 3 and "A" <= p[0] <= "H" and p[1] in "12345" and "X" <= p[2] <= "Z" for p in plan):
            return None
        if len({p[0] for p in plan}) != len(plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [s["id"] for s in world["data"]["ships"]]
        yards = [y["id"] for y in world["data"]["yards"]]
        n_waves = world["data"]["n_waves"]
        choices = [str(w) + y for w in range(1, n_waves + 1) for y in yards]
        for assign in itertools.product(choices, repeat=len(ids)):
            yield tuple(s + c for s, c in zip(ids, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        ships = {s["id"]: s for s in world["data"]["ships"]}
        yards = {y["id"] for y in world["data"]["yards"]}
        n_waves = world["data"]["n_waves"]
        parsed = _parse(plan, ships, yards, n_waves)
        if parsed is None:
            return None
        cap = world["modules"]["wave"]["cap"]
        yard = world["modules"].get("yard")
        thresh = yard["thresh"] if yard else 10**9
        slow = yard["slow"] if yard else 0
        ends = world["data"]["wave_end"]
        used = [0] * n_waves
        stock = {y: 0 for y in yards}
        over = late_n = 0
        fired: set[str] = {"wave"}
        order = [(ships[sid]["seq"], sid, w, y) for sid, w, y in parsed]
        order.sort()
        for _seq, sid, w, y in order:
            ship = ships[sid]
            placed = _place(used, w, ship["boxes"], cap)
            if placed is None:
                return None
            used, last = placed
            extra = 0
            if stock[y] >= thresh:
                extra = slow
                fired.add("yard")
            done = ends[last] + extra
            stock[y] += ship["boxes"]
            miss = done - ship["tide"]
            if miss > 0:
                over += miss
                late_n += 1
        return Outcome(tuple(plan), {"over": over, "late_n": late_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        ships = [[s["id"], s["boxes"], s["tide"]] for s in d["ships"]]
        yards = [y["id"] for y in d["yards"]]
        ends = [[i + 1, t] for i, t in enumerate(d["wave_end"])]
        return "\n".join([
            "你是港口堆场调度。船已经靠好，只决定每艘船的箱子进哪个箱区、走哪一波集卡。",
            f"船舶表按进场先后，每行 `[编号, 箱量, 潮汐时限]`：{_c(ships)}。进场先后固定，不能改船序。",
            f"箱区编号：{_c(yards)}。波次完成时刻每行 `[波次, 分钟]`：{_c(ends)}。",
            "答题记号：每艘船写「编号+波次+箱区」，按船舶表顺序用短横线连接，例如 A1X-B2Y。每艘船恰好一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个方案并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "over", "points": 6,
             "text": "给出最优方案，记号如 A1X-B2Y-C1X。"},
            {"name": "over", "metric": "over", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_over", "metric": "over", "points": 5, "cf": "thresh_shift"},
        ]


FAMILY = YardFamily()
