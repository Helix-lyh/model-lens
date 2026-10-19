"""产线班次：批次进场顺序已定。每笔只选产线和班次。上一班占用会压缩本班容量。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选产线", "选班次")


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_lag(p, w):
    cap = w["data"]["cap"]
    return (f"班次容量：每条产线每一班最多消化 {cap} 个占用。某一班的有效容量还要扣掉"
            f"「同一产线上一班占用 × {p['k']}」，扣完小于 0 按 0。"
            f"这一班占用超过有效容量时，该班上每一笔的完成时刻都再加 {p['slow']} 分钟；"
            "超出的占用也计入总逾期。")


def _t_setup(p, _w):
    return (f"换族：同一产线上，后一笔与刚做完的产品族不同时，后一笔占用在加工分钟上再加 {p['minutes']}。"
            "产品族相同，或这条产线还没做过，不加。换族占用算进班次占用。")


MODULES = {m.id: m for m in [
    Module("lag", "班次容量", 10, _t_lag),
    Module("setup", "换族", 20, _t_setup),
]}

METRICS = {
    "over": "总逾期分钟（各批次完成时刻超出交期的部分之和，未超出记 0）",
    "late_n": "逾期批次数",
}

OBJECTIVE_PHRASES = {
    "over": "总逾期分钟最小",
    "late_n": "逾期批次数最小",
}


def _k_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    lag = x["modules"]["lag"]
    x["modules"]["lag"] = {**lag, "k": lag["alt"]}
    return x


COUNTERFACTUALS = {
    "k_shift": Counterfactual(
        _k_shift,
        lambda w: f"若上一班占用的扣除倍数改为 {w['modules']['lag']['alt']}（其余不变），",
    ),
}

READINGS: dict = {}


def _parse(plan: tuple, jobs: dict, lines: set[str], n_waves: int) -> list[tuple[str, int, str]] | None:
    if len(plan) != len(jobs):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 3 or tok[0] not in jobs:
            return None
        if tok[0] in seen:
            return None
        if not tok[1].isdigit() or not (1 <= int(tok[1]) <= n_waves):
            return None
        if tok[2] not in lines:
            return None
        seen.add(tok[0])
        out.append((tok[0], int(tok[1]) - 1, tok[2]))
    if seen != set(jobs):
        return None
    return out


def greedy_earliest(world: dict) -> tuple:
    """每笔单独看：最早班次、当前占用更少的产线。"""
    jobs = world["data"]["jobs"]
    lines = [ln["id"] for ln in world["data"]["lines"]]
    n_waves = world["data"]["n_waves"]
    load = {ln: [0] * n_waves for ln in lines}
    last_fam = {ln: None for ln in lines}
    plan = []
    setup = world["modules"].get("setup", {}).get("minutes", 0)
    for job in jobs:
        chosen = None
        for w in range(n_waves):
            line = min(lines, key=lambda ln: (load[ln][w], ln))
            chosen = (w, line)
            break
        w, line = chosen
        extra = setup if last_fam[line] and last_fam[line] != job["family"] else 0
        load[line][w] += job["minutes"] + extra
        last_fam[line] = job["family"]
        plan.append(job["id"] + str(w + 1) + line)
    return tuple(plan)


class ShiftFamily:
    id = "shift"
    primary = "over"
    shared = "late_n"
    cf_key = "k_shift"
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
        ids = [j["id"] for j in world["data"]["jobs"]]
        lines = [ln["id"] for ln in world["data"]["lines"]]
        n_waves = world["data"]["n_waves"]
        choices = [str(w) + ln for w in range(1, n_waves + 1) for ln in lines]
        for assign in itertools.product(choices, repeat=len(ids)):
            yield tuple(s + c for s, c in zip(ids, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        jobs = {j["id"]: j for j in world["data"]["jobs"]}
        lines = {ln["id"] for ln in world["data"]["lines"]}
        n_waves = world["data"]["n_waves"]
        parsed = _parse(plan, jobs, lines, n_waves)
        if parsed is None:
            return None
        cap = world["data"]["cap"]
        lag = world["modules"].get("lag")
        k = lag["k"] if lag else 0
        slow = lag["slow"] if lag else 0
        setup_m = world["modules"].get("setup", {}).get("minutes", 0)
        ends = world["data"]["wave_end"]
        load = {ln: [0] * n_waves for ln in lines}
        last_fam: dict[str, str | None] = {ln: None for ln in lines}
        fired: set[str] = set()
        if lag:
            fired.add("lag")
        order = [(jobs[sid]["seq"], sid, w, ln) for sid, w, ln in parsed]
        order.sort()
        for _seq, sid, w, ln in order:
            job = jobs[sid]
            extra = 0
            if last_fam[ln] and last_fam[ln] != job["family"]:
                extra = setup_m
                fired.add("setup")
            load[ln][w] += job["minutes"] + extra
            last_fam[ln] = job["family"]
        over = late_n = 0
        for sid, w, ln in parsed:
            cap_eff = cap if w == 0 else max(0, cap - k * load[ln][w - 1])
            done = ends[w]
            if load[ln][w] > cap_eff:
                done += slow
            miss = done - jobs[sid]["due"]
            if miss > 0:
                over += miss
                late_n += 1
            over += max(0, load[ln][w] - cap_eff)
        return Outcome(tuple(plan), {"over": over, "late_n": late_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        jobs = [[j["id"], j["family"], j["minutes"], j["due"]] for j in d["jobs"]]
        lines = [ln["id"] for ln in d["lines"]]
        ends = [[i + 1, t] for i, t in enumerate(d["wave_end"])]
        return "\n".join([
            "你是产线调度。批次已经按进场排好，只决定每一笔进哪条产线、放进哪一班。",
            f"批次表按进场先后，每行 `[编号, 产品族, 加工分钟, 交期]`：{_c(jobs)}。进场先后固定，不能改批次顺序。",
            f"产线编号：{_c(lines)}。班次完成时刻每行 `[班次, 分钟]`：{_c(ends)}。",
            "一笔的完成时刻先取它所在班次的完成时刻。答题记号：每笔写「编号+班次+产线」，按批次表顺序用短横线连接，例如 A1X-B2Y。每笔恰好一次。",
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
            {"name": "cf_over", "metric": "over", "points": 5, "cf": "k_shift"},
        ]


FAMILY = ShiftFamily()
