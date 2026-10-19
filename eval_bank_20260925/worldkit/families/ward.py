"""急诊床位：一张普通床、一张隔离床，决定患者开始处置的顺序。隔离患者离开后要消毒。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome
from eval_bank_20260925.worldkit.share import dual_progress

DECISIONS = ("选处置顺序",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_clean(p, _w):
    return (f"终末消毒：隔离患者离开隔离床后，该床加 {p['minutes']} 分钟消毒，消毒结束前不能再接待患者。"
            "普通床不消毒。非隔离患者若占用了隔离床，离开后同样要消毒。")


def _t_doctor(p, _w):
    return f"医生到岗：任何患者开始处置的时刻不得早于 {p['at']} 分钟。床位更早空出时也要等到这个时刻。"


def _t_mix(p, _w):
    return (f"交叉消毒：隔离床只消毒一次，时长等下一位患者确定后才知道，不在终末消毒的分钟之外再叠加一遍。"
            f"下一位分级与刚离开的相同，这一次消毒就等于终末消毒的分钟；"
            f"分级不同，这一次消毒等于终末消毒的分钟再加 {p['extra']} 分钟。"
            "第一位使用隔离床的患者之前不消毒。普通床不消毒。")


def _t_nurse(_p, _w):
    return ("护理：两张床都有患者的每一分钟，两名患者都只累积半格处置，同一人累积满 2 分钟才算完成 1 个占用单位。"
            "某一分钟只有一张床有患者时，该患者该分钟完成 1 个占用单位，此前未满的半格清零。"
            "占用单位等于患者表里的占用分钟。")


MODULES = {m.id: m for m in [
    Module("clean", "终末消毒", 10, _t_clean),
    Module("mix", "交叉消毒", 15, _t_mix),
    Module("doctor", "医生到岗", 20, _t_doctor),
    Module("nurse", "护理", 25, _t_nurse),
]}

METRICS = {
    "excess": "总超出分钟（各患者开始时刻超出其时限的部分之和，未超出记 0）",
    "late_n": "超出时限的患者数",
}

OBJECTIVE_PHRASES = {
    "excess": "总超出分钟最小",
    "late_n": "超出时限的患者数最小",
}


def _doctor_early(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"]["doctor"]["at"] = x["modules"]["doctor"]["early"]
    return x


def _no_mix(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("mix", None)
    return x


COUNTERFACTUALS = {
    "doctor_early": Counterfactual(
        _doctor_early,
        lambda w: f"若医生改为 {w['modules']['doctor']['early']} 分钟到岗（其余不变），",
    ),
    "no_mix": Counterfactual(_no_mix, lambda _w: "若取消交叉消毒、隔离床只做终末消毒，"),
}

READINGS: dict = {}


def _metrics(world: dict, plan: tuple) -> dict[str, int] | None:
    patients = {p["id"]: p for p in world["data"]["patients"]}
    if len(plan) != len(patients) or set(plan) != set(patients):
        return None
    mods = world["modules"]
    doctor = mods["doctor"]["at"] if "doctor" in mods else 0
    clean = mods["clean"]["minutes"] if "clean" in mods else 0
    extra = mods["mix"]["extra"] if "mix" in mods else 0
    share = "nurse" in mods
    normal = iso_leave = 0
    prev = None
    mixed = False
    starts: list[int] = []
    beds: list[int] = []
    needs: list[int] = []
    pids: list[str] = []
    done: list[int] = []
    for pid in plan:
        p = patients[pid]
        earliest = max(p["arrive"], doctor)
        if prev is None:
            iso_add = 0
        else:
            iso_add = clean
            if extra and p["grade"] != prev:
                iso_add += extra
                mixed = True
        iso_start = max(earliest, iso_leave + iso_add)
        if p["iso"]:
            start = iso_start
            bed = 1
            prev = p["grade"] if extra else ""
        else:
            normal_start = max(earliest, normal)
            if normal_start <= iso_start:
                start = normal_start
                bed = 0
            else:
                start = iso_start
                bed = 1
                prev = p["grade"] if extra else ""
        pids.append(pid)
        starts.append(start)
        beds.append(bed)
        needs.append(p["stay"])
        if share:
            done = dual_progress(starts, beds, needs, True)
        else:
            done = [s + n for s, n in zip(starts, needs)]
        normal = iso_leave = 0
        for i, end in enumerate(done):
            if beds[i] == 0:
                normal = max(normal, end)
            else:
                iso_leave = max(iso_leave, end)
    excess = late_n = 0
    for pid, start in zip(pids, starts):
        p = patients[pid]
        over = start - (p["arrive"] + p["limit"])
        if over > 0:
            excess += over
            late_n += 1
    return {"excess": excess, "late_n": late_n, "_mixed": int(mixed)}


def greedy_urgent(world: dict) -> tuple:
    patients = world["data"]["patients"]
    return tuple(p["id"] for p in sorted(patients, key=lambda p: (p["arrive"] + p["limit"], p["id"])))


def greedy_batch(world: dict) -> tuple:
    """同一分级做完再换。不计交叉消毒比插队更贵。"""
    patients = world["data"]["patients"]
    return tuple(p["id"] for p in sorted(patients, key=lambda p: (p["grade"], p["arrive"] + p["limit"], p["id"])))


def _greedies(world: dict) -> list[tuple]:
    out = [greedy_urgent(world)]
    if "mix" in world["modules"]:
        out.insert(0, greedy_batch(world))
    return out


class WardFamily:
    id = "ward"
    primary = "excess"
    shared = "late_n"
    cf_key = "doctor_early"
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
        ids = [p["id"] for p in world["data"]["patients"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        metrics = _metrics(world, plan)
        if metrics is None:
            return None
        mixed = metrics.pop("_mixed")
        fired = set()
        if "clean" in world["modules"]:
            fired.add("clean")
        if mixed:
            fired.add("mix")
        if "doctor" in world["modules"]:
            fired.add("doctor")
        if "nurse" in world["modules"]:
            fired.add("nurse")
        return Outcome(tuple(plan), metrics, [], frozenset(fired))

    def header(self, world: dict) -> str:
        mixed = "mix" in world["modules"]
        if mixed:
            rows = [[p["id"], p["arrive"], p["limit"], p["stay"], "隔离" if p["iso"] else "普通", p["grade"]] for p in world["data"]["patients"]]
            table = f"患者表每行 `[编号, 到达分钟, 时限分钟, 占用分钟, 类型, 分级]`：{_c(rows)}。"
            clock = ("开始时刻取到达、医生到岗、该床可开始 三者最晚。"
                     "普通床在上一位离开时即可开始。隔离床可开始时刻为上一位离开再加上本次消毒分钟；没有上一位则从 0。")
        else:
            rows = [[p["id"], p["arrive"], p["limit"], p["stay"], "隔离" if p["iso"] else "普通"] for p in world["data"]["patients"]]
            table = f"患者表每行 `[编号, 到达分钟, 时限分钟, 占用分钟, 类型]`：{_c(rows)}。"
            clock = ("开始时刻取到达、医生到岗、该床空闲 三者最晚。"
                     "占用结束后该床空出；隔离床若本段规则要求消毒，空出时刻再顺延消毒分钟。")
        return "\n".join([
            "你是急诊分诊台。现在有一张普通床、一张隔离床，决定患者开始处置的顺序。",
            table,
            "时限从到达分钟起算：开始时刻晚于到达 + 时限，超出部分记入总超出。",
            "隔离患者只能用隔离床。其他患者优先用普通床；仅当普通床的开始时刻晚于隔离床时，才改用隔离床。",
            clock,
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个顺序并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "excess", "points": 6,
             "text": "给出最优处置顺序，患者编号用短横线连接，例如 A-B-C-D-E-F。"},
            {"name": "excess", "metric": "excess", "points": 5},
            {"name": "late_n", "metric": "late_n", "points": 4},
            {"name": "cf_excess", "metric": "excess", "points": 5, "cf": "doctor_early"},
        ]


FAMILY = WardFamily()
