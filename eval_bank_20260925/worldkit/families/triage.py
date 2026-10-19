"""急诊分诊：患者到达顺序已定。每人只选床位和开始时段。一张床装不下的占用整段挤到后面时段。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选床位", "选开始时段")


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_slot(p, _w):
    return (f"床位时段：每张床每一时段最多消化 {p['cap']} 个占用。一名患者从他选定的开始时段起占用这张床，"
            "这一时段装不下的整段余量挤到这张床后面的时段，直到装完。"
            "完成时段是最后装上余量的那一时段。后面再也装不下则该方案不可行。")


def _t_mix(p, _w):
    return (f"交叉消毒：同一张床上，后一名与刚离开的分级不同时，后一名占用在处置分钟上再加 {p['extra']}。"
            "分级相同，或这张床还没接待过，不加。交叉占用算进时段占用。")


MODULES = {m.id: m for m in [
    Module("slot", "床位时段", 10, _t_slot),
    Module("mix", "交叉消毒", 20, _t_mix),
]}

METRICS = {
    "excess": "总超出分钟（各患者完成时刻超出时限的部分之和，未超出记 0）",
    "late_n": "超出时限的患者数",
}

OBJECTIVE_PHRASES = {
    "excess": "总超出分钟最小",
    "late_n": "超出时限的患者数最小",
}


def _mix_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    mix = x["modules"]["mix"]
    x["modules"]["mix"] = {**mix, "extra": mix["alt"]}
    return x


COUNTERFACTUALS = {
    "mix_shift": Counterfactual(
        _mix_shift,
        lambda w: f"若交叉消毒改为加 {w['modules']['mix']['alt']} 分钟（其余不变），",
    ),
}

READINGS: dict = {}


def _parse(plan: tuple, patients: dict, beds: set[str], n_slots: int) -> list[tuple[str, int, str]] | None:
    if len(plan) != len(patients):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 3 or tok[0] not in patients:
            return None
        if tok[0] in seen:
            return None
        if not tok[1].isdigit() or not (1 <= int(tok[1]) <= n_slots):
            return None
        if tok[2] not in beds:
            return None
        seen.add(tok[0])
        out.append((tok[0], int(tok[1]) - 1, tok[2]))
    if seen != set(patients):
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
    """每人单独看：能一次装进的最早时段，占用更少的床。"""
    patients = world["data"]["patients"]
    beds = [b["id"] for b in world["data"]["beds"]]
    cap = world["modules"]["slot"]["cap"]
    n_slots = world["data"]["n_slots"]
    used = {b: [0] * n_slots for b in beds}
    last_g = {b: None for b in beds}
    mix = world["modules"].get("mix", {}).get("extra", 0)
    plan = []
    for p in patients:
        chosen = None
        extra = 0
        for w in range(n_slots):
            bed = min(beds, key=lambda b: (used[b][w], b))
            extra = mix if last_g[bed] and last_g[bed] != p["grade"] else 0
            if cap - used[bed][w] >= p["care"] + extra:
                chosen = (w, bed, extra)
                break
        if chosen is None:
            bed = min(beds, key=lambda b: (sum(used[b]), b))
            extra = mix if last_g[bed] and last_g[bed] != p["grade"] else 0
            chosen = (n_slots - 1, bed, extra)
        w, bed, extra = chosen
        placed = _place(used[bed], w, p["care"] + extra, cap)
        if placed:
            used[bed], _ = placed
        last_g[bed] = p["grade"]
        plan.append(p["id"] + str(w + 1) + bed)
    return tuple(plan)


class TriageFamily:
    id = "triage"
    primary = "excess"
    shared = "late_n"
    cf_key = "mix_shift"
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
        if not all(len(p) == 3 and "A" <= p[0] <= "H" and p[1] in "12345" and p[2] in "NI" for p in plan):
            return None
        if len({p[0] for p in plan}) != len(plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [p["id"] for p in world["data"]["patients"]]
        beds = [b["id"] for b in world["data"]["beds"]]
        n_slots = world["data"]["n_slots"]
        choices = [str(w) + b for w in range(1, n_slots + 1) for b in beds]
        for assign in itertools.product(choices, repeat=len(ids)):
            yield tuple(s + c for s, c in zip(ids, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        patients = {p["id"]: p for p in world["data"]["patients"]}
        beds = {b["id"] for b in world["data"]["beds"]}
        n_slots = world["data"]["n_slots"]
        parsed = _parse(plan, patients, beds, n_slots)
        if parsed is None:
            return None
        cap = world["modules"]["slot"]["cap"]
        mix_m = world["modules"].get("mix", {}).get("extra", 0)
        ends = world["data"]["slot_end"]
        used = {b: [0] * n_slots for b in beds}
        last_g: dict[str, str | None] = {b: None for b in beds}
        excess = late_n = 0
        fired: set[str] = {"slot"}
        order = [(patients[sid]["seq"], sid, w, b) for sid, w, b in parsed]
        order.sort()
        for _seq, sid, w, b in order:
            p = patients[sid]
            extra = 0
            if last_g[b] and last_g[b] != p["grade"]:
                extra = mix_m
                fired.add("mix")
            placed = _place(used[b], w, p["care"] + extra, cap)
            if placed is None:
                return None
            used[b], last = placed
            done = ends[last]
            miss = done - p["limit"]
            if miss > 0:
                excess += miss
                late_n += 1
            last_g[b] = p["grade"]
        return Outcome(tuple(plan), {"excess": excess, "late_n": late_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        rows = [[p["id"], p["grade"], p["care"], p["limit"]] for p in d["patients"]]
        beds = [b["id"] for b in d["beds"]]
        ends = [[i + 1, t] for i, t in enumerate(d["slot_end"])]
        return "\n".join([
            "你是急诊分诊。患者已经按到达排好，只决定每人进哪张床、从哪一时段开始处置。",
            f"患者表按到达先后，每行 `[编号, 分级, 处置分钟, 时限]`：{_c(rows)}。到达先后固定，不能改患者顺序。",
            f"床位编号：{_c(beds)}。N 普通床，I 隔离床。时段完成时刻每行 `[时段, 分钟]`：{_c(ends)}。",
            "答题记号：每人写「编号+开始时段+床位」，按患者表顺序用短横线连接，例如 A1I-B2N。每人恰好一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个方案并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "excess", "points": 6,
             "text": "给出最优方案，记号如 A1I-B2N-C1I。"},
            {"name": "excess", "metric": "excess", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_excess", "metric": "excess", "points": 5, "cf": "mix_shift"},
        ]


FAMILY = TriageFamily()
