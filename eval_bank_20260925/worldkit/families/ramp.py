"""机坪波次：航班离港顺序已定。每架只选拖车和开始波次。一辆车装不下的占用整段挤到后面波次。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选拖车", "选开始波次")


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_wave(p, _w):
    return (f"拖车波次：每辆拖车每一波最多消化 {p['cap']} 个拖车单位。一架航班从它选定的开始波次起占用这辆车，"
            "这一波装不下的整段余量挤到这辆车后面的波次，直到装完。"
            "完成波次是最后装上余量的那一波。后面再也装不下则该方案不可行。")


def _t_zone(p, _w):
    return (f"换区：同一辆拖车上，后一架的停机区与刚完成的不同时，后一架占用在拖车单位上再加 {p['minutes']}。"
            "停机区相同，或这辆车还没拖过，不加。换区占用算进波次占用。")


MODULES = {m.id: m for m in [
    Module("wave", "拖车波次", 10, _t_wave),
    Module("zone", "换区", 20, _t_zone),
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
        lambda w: f"若换区占用改为 {w['modules']['zone']['alt']}（其余不变），",
    ),
}

READINGS: dict = {}


def _parse(plan: tuple, flights: dict, tractors: set[str], n_waves: int) -> list[tuple[str, int, str]] | None:
    if len(plan) != len(flights):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 3 or tok[0] not in flights:
            return None
        if tok[0] in seen:
            return None
        if not tok[1].isdigit() or not (1 <= int(tok[1]) <= n_waves):
            return None
        if tok[2] not in tractors:
            return None
        seen.add(tok[0])
        out.append((tok[0], int(tok[1]) - 1, tok[2]))
    if seen != set(flights):
        return None
    return out


def _place(used: list[int], start: int, need: int, cap: int) -> tuple[list[int], int] | None:
    remaining = need
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
    """每架单独看：能一次装进的最早波次，占用更少的拖车。"""
    flights = world["data"]["flights"]
    tractors = [t["id"] for t in world["data"]["tractors"]]
    cap = world["modules"]["wave"]["cap"]
    n_waves = world["data"]["n_waves"]
    used = {t: [0] * n_waves for t in tractors}
    last_z = {t: None for t in tractors}
    gap = world["modules"].get("zone", {}).get("minutes", 0)
    plan = []
    for f in flights:
        chosen = None
        extra = 0
        for w in range(n_waves):
            tr = min(tractors, key=lambda t: (used[t][w], t))
            extra = gap if last_z[tr] and last_z[tr] != f["zone"] else 0
            if cap - used[tr][w] >= f["tow"] + extra:
                chosen = (w, tr, extra)
                break
        if chosen is None:
            tr = min(tractors, key=lambda t: (sum(used[t]), t))
            extra = gap if last_z[tr] and last_z[tr] != f["zone"] else 0
            chosen = (n_waves - 1, tr, extra)
        w, tr, extra = chosen
        placed = _place(used[tr], w, f["tow"] + extra, cap)
        if placed:
            used[tr], _ = placed
        last_z[tr] = f["zone"]
        plan.append(f["id"] + str(w + 1) + tr)
    return tuple(plan)


class RampFamily:
    id = "ramp"
    primary = "flow"
    shared = "late_n"
    cf_key = "zone_shift"
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
        ids = [f["id"] for f in world["data"]["flights"]]
        tractors = [t["id"] for t in world["data"]["tractors"]]
        n_waves = world["data"]["n_waves"]
        choices = [str(w) + t for w in range(1, n_waves + 1) for t in tractors]
        for assign in itertools.product(choices, repeat=len(ids)):
            yield tuple(s + c for s, c in zip(ids, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        flights = {f["id"]: f for f in world["data"]["flights"]}
        tractors = {t["id"] for t in world["data"]["tractors"]}
        n_waves = world["data"]["n_waves"]
        parsed = _parse(plan, flights, tractors, n_waves)
        if parsed is None:
            return None
        cap = world["modules"]["wave"]["cap"]
        gap = world["modules"].get("zone", {}).get("minutes", 0)
        ends = world["data"]["wave_end"]
        used = {t: [0] * n_waves for t in tractors}
        last_z: dict[str, str | None] = {t: None for t in tractors}
        flow = late_n = 0
        fired: set[str] = {"wave"}
        order = [(flights[sid]["seq"], sid, w, t) for sid, w, t in parsed]
        order.sort()
        for _seq, sid, w, t in order:
            f = flights[sid]
            extra = 0
            if last_z[t] and last_z[t] != f["zone"]:
                extra = gap
                fired.add("zone")
            placed = _place(used[t], w, f["tow"] + extra, cap)
            if placed is None:
                return None
            used[t], last = placed
            done = ends[last]
            flow += done
            if done > f["dep"]:
                late_n += 1
            last_z[t] = f["zone"]
        return Outcome(tuple(plan), {"flow": flow, "late_n": late_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        rows = [[f["id"], f["dep"], f["tow"], f["zone"]] for f in d["flights"]]
        tractors = [t["id"] for t in d["tractors"]]
        ends = [[i + 1, t] for i, t in enumerate(d["wave_end"])]
        return "\n".join([
            "你排机坪推出。航班已经按计划离港排好，只决定每架挂哪辆拖车、从哪一波开始。",
            f"航班表按计划离港先后，每行 `[编号, 计划离港分钟, 拖车单位, 停机区]`：{_c(rows)}。这个先后固定，不能改航班顺序。",
            f"拖车编号：{_c(tractors)}。波次完成时刻每行 `[波次, 分钟]`：{_c(ends)}。",
            "答题记号：每架写「编号+开始波次+拖车」，按航班表顺序用短横线连接，例如 A1X-B2Y。每架恰好一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个方案并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "flow", "points": 6,
             "text": "给出最优方案，记号如 A1X-B2Y-C1X。"},
            {"name": "flow", "metric": "flow", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_flow", "metric": "flow", "points": 5, "cf": "zone_shift"},
        ]


FAMILY = RampFamily()
