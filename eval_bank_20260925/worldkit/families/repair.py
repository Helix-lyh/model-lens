"""电网抢修：两个班组。方案同时选定工单由谁做，以及派工顺序。"""
from __future__ import annotations

import copy
import itertools
import json
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("选班组", "选派工顺序")


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_fatigue(p, _w):
    return (f"夜班：从第 {p['at']} 分钟起（含这一分钟），作业进度每分钟只完成半个作业单位，"
            "累计满 2 分钟才完成 1 个单位。路程仍按原分钟。"
            "若一单作业跨过这个时刻，时刻之前按满速，之后按半速。")


def _t_clash(p, _w):
    return ("同站互斥：同一地点同一时刻只能有一个班组作业。后到的班组等到先到的班组做完才能开工。"
            "路程可以重叠。起点仓库不受这条限制。")


def _t_extra(p, _w):
    return f"加项：每张工单的作业单位在表中数值上再加 {p['extra']} 个。夜班半速按加完之后的作业单位计算。"


MODULES = {m.id: m for m in [
    Module("clash", "同站互斥", 10, _t_clash),
    Module("fatigue", "夜班", 15, _t_fatigue),
    Module("extra", "加项", 20, _t_extra),
]}

METRICS = {
    "late": "总迟到分钟（各单完工时刻超出时限的部分之和，提前完工记 0）",
    "late_n": "迟到工单数",
}

OBJECTIVE_PHRASES = {
    "late": "总迟到分钟最小",
    "late_n": "迟到工单数最小",
}


def _no_extra(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("extra", None)
    return x


COUNTERFACTUALS = {
    "no_extra": Counterfactual(_no_extra, lambda _w: "若取消加项、作业单位恢复为表中数值，"),
}

READINGS: dict = {}


def _parse(plan: tuple, jobs: dict, crews: dict) -> list[tuple[str, str]] | None:
    if len(plan) != len(jobs):
        return None
    seen: set[str] = set()
    out = []
    for tok in plan:
        if len(tok) != 2 or tok[0] not in jobs or tok[1] not in crews:
            return None
        if tok[0] in seen:
            return None
        seen.add(tok[0])
        out.append((tok[0], tok[1]))
    if seen != set(jobs):
        return None
    return out


def _travel(world: dict, a: str, b: str) -> int:
    return world["data"]["travel"][a][b]


def _finish(start: int, work: int, fatigue_at: int | None) -> tuple[int, bool]:
    if work <= 0:
        return start, False
    if fatigue_at is None or start + work <= fatigue_at:
        return start + work, False
    if start >= fatigue_at:
        return start + 2 * work, True
    full = fatigue_at - start
    remain = work - full
    return fatigue_at + 2 * remain, True


def greedy_due(world: dict) -> tuple:
    """时限紧的先派；专长对口的班组优先，不计路程和夜班。"""
    crews = world["data"]["crews"]
    jobs = sorted(world["data"]["jobs"], key=lambda j: (j["due"], j["id"]))
    plan = []
    for job in jobs:
        fit = [c for c in crews if job["skill"] in c["skills"]]
        chosen = min(fit, key=lambda c: (len(c["skills"]), c["id"]))
        plan.append(job["id"] + chosen["id"])
    return tuple(plan)


class RepairFamily:
    id = "repair"
    primary = "late"
    shared = "late_n"
    cf_key = "no_extra"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS
    greedies = staticmethod(lambda w: [greedy_due(w)])

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        if len(plan) < 2 or len(set(plan)) != len(plan):
            return None
        if not all(len(p) == 2 and "A" <= p[0] <= "H" and p[1] in "12" for p in plan):
            return None
        if len({p[0] for p in plan}) != len(plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        jobs = world["data"]["jobs"]
        crews = world["data"]["crews"]
        options = []
        for job in jobs:
            fit = [c["id"] for c in crews if job["skill"] in c["skills"]]
            if not fit:
                return
            options.append(fit)
        ids = [j["id"] for j in jobs]
        for order in itertools.permutations(ids):
            index = {j["id"]: i for i, j in enumerate(jobs)}
            slots = [options[index[j]] for j in order]
            for assign in itertools.product(*slots):
                yield tuple(j + c for j, c in zip(order, assign))

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        return _simulate(world, plan)

    def header(self, world: dict) -> str:
        d = world["data"]
        crews = [[c["id"], "、".join(c["skills"])] for c in d["crews"]]
        jobs = [[j["id"], j["site"], j["skill"], j["work"], j["due"]] for j in d["jobs"]]
        sites = sorted({j["site"] for j in d["jobs"]} | {d["depot"]})
        travel = [[a, b, d["travel"][a][b]] for a in sites for b in sites if a != b]
        return "\n".join([
            "你派两个抢修班组。决定每张工单由哪个班组做，以及派工的先后。",
            f"班组表每行 `[编号, 技能]`：{_c(crews)}。两个班组 0 分钟都在地点 {d['depot']}。",
            f"工单表每行 `[编号, 地点, 所需技能, 作业单位, 时限]`：{_c(jobs)}。",
            f"路程表每行 `[起点, 终点, 分钟]`：{_c(travel)}。同一地点之间路程为 0。",
            "每个班组按你写下的、属于自己的那些工单依次执行。开工时刻 = max(本班组到达该地点的分钟, 该地点空闲分钟)。"
            "到达分钟 = 本班组上一单完工分钟 + 路程；第一单从仓库出发。"
            "满速时每分钟完成 1 个作业单位。班组技能不含该单所需技能则方案不可行。"
            "迟到分钟 = max(0, 完工时刻 − 时限)。",
            "答题记号：每张工单写「编号+班组编号」，按派工先后用短横线连接，例如 A1-B2-C1。每张工单恰好出现一次。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "late", "points": 6,
             "text": "给出最优方案，记号如 A1-B2-C1。"},
            {"name": "late", "metric": "late", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_late", "metric": "late", "points": 5, "cf": "no_extra"},
        ]


FAMILY = RepairFamily()


def _simulate(world: dict, plan: tuple) -> Outcome | None:
    jobs = {j["id"]: j for j in world["data"]["jobs"]}
    crews = {c["id"]: c for c in world["data"]["crews"]}
    parsed = _parse(plan, jobs, crews)
    if parsed is None:
        return None
    mods = world["modules"]
    clash = "clash" in mods
    fatigue_at = mods["fatigue"]["at"] if "fatigue" in mods else None
    extra = mods["extra"]["extra"] if "extra" in mods else 0
    depot = world["data"]["depot"]
    clock = {c: 0 for c in crews}
    site = {c: depot for c in crews}
    site_free = {depot: 0}
    late = late_n = 0
    fired: set[str] = set()
    for jid, cid in parsed:
        job = jobs[jid]
        crew = crews[cid]
        if job["skill"] not in crew["skills"]:
            return None
        start = clock[cid] + _travel(world, site[cid], job["site"])
        if clash:
            occupied = site_free.get(job["site"], 0)
            if start < occupied:
                start = occupied
                fired.add("clash")
        done, used = _finish(start, job["work"] + extra, fatigue_at)
        if used:
            fired.add("fatigue")
        clock[cid] = done
        site[cid] = job["site"]
        if clash:
            site_free[job["site"]] = done
        over = done - job["due"]
        if over > 0:
            late += over
            late_n += 1
    if extra:
        fired.add("extra")
    return Outcome(tuple(plan), {"late": late, "late_n": late_n}, [], frozenset(fired))
