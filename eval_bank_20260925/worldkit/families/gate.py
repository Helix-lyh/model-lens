"""登机口指派：把同时段航班分到靠桥或远机位。宽体机占用重叠时不能停在相邻机位。"""
from __future__ import annotations

import copy
import itertools
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome
from eval_bank_20260925.worldkit.share import dual_progress

DECISIONS = ("选机位",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_wide(_p, _w):
    return "宽体限制：两架宽体航班的占用区间若重叠，不得停在相邻机位。相邻关系见机位表。"


def _t_wave(p, _w):
    return (f"摆渡波次：波次取离开分钟整除 {p['width']} 的商，商相同的远机位航班是同一波。"
            f"同一波内按航班表的先后，排在最前的一架按机位表的人均摆渡分钟计费，其余每架再加 {p['extra']}。"
            f"宽度为 {p['width']} 时，离开 {p['width'] - 1} 与 {p['width']} 不是同一波。靠桥机位不加价，也不占波次名额。")


def _t_tow(p, _w):
    return (f"拖车：远机位航班离开前要占用拖车 {p['minutes']} 分钟。两辆拖车。"
            "按航班表顺序，每架远机位航班挂到当前更早空闲的拖车；两车同时空闲时挂甲车。"
            "两辆拖车都在作业的每一分钟，两架航班都只累积半格，同一架累积满 2 分钟才完成 1 个拖车单位。"
            "只有一辆在作业时，该分钟完成 1 个单位，未满的半格清零。"
            "靠桥不占拖车。拖车开始时刻取航班到达与该车空闲的较晚者。"
            "若拖车完成晚于离开分钟，超出的每分钟按该航班旅客数计入总摆渡分钟。")


MODULES = {m.id: m for m in [
    Module("wide", "宽体相邻限制", 10, _t_wide),
    Module("wave", "摆渡波次", 20, _t_wave),
    Module("tow", "拖车", 25, _t_tow),
]}

METRICS = {
    "pax_bus": "总摆渡分钟（各航班旅客数乘以该航班实际人均摆渡分钟后求和；没有波次加价时，实际值等于机位表）",
    "remote_n": "使用远机位的航班数",
}

OBJECTIVE_PHRASES = {
    "pax_bus": "总摆渡分钟最小",
    "remote_n": "远机位航班数最小",
}


def _no_wide(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("wide", None)
    return x


def _tow_shift(world: dict) -> dict:
    x = copy.deepcopy(world)
    tow = x["modules"]["tow"]
    x["modules"]["tow"] = {**tow, "minutes": tow["alt"]}
    return x


COUNTERFACTUALS = {
    "no_wide": Counterfactual(_no_wide, lambda _w: "若取消宽体相邻限制，"),
    "tow_shift": Counterfactual(
        _tow_shift,
        lambda w: f"若每架远机位占用拖车改为 {w['modules']['tow']['alt']} 分钟（其余不变），",
    ),
}

READINGS: dict = {}


def _overlap(a: dict, b: dict) -> bool:
    return a["arr"] < b["dep"] and b["arr"] < a["dep"]


def _fits(world: dict, pairs: list[tuple[dict, dict]]) -> bool:
    gates = {g["id"]: g for g in world["data"]["gates"]}
    wide_on = "wide" in world["modules"]
    for i, (f1, g1) in enumerate(pairs):
        for f2, g2 in pairs[i + 1:]:
            if g1["id"] == g2["id"] and _overlap(f1, f2):
                return False
            if wide_on and f1["wide"] and f2["wide"] and _overlap(f1, f2):
                if g2["id"] in gates[g1["id"]]["adj"] or g1["id"] in gates[g2["id"]]["adj"]:
                    return False
    return True


def greedy_bridge(world: dict) -> tuple | None:
    """先占靠桥机位，编号小的优先。"""
    flights = world["data"]["flights"]
    gates = sorted(world["data"]["gates"], key=lambda g: (g["remote"], g["id"]))
    used: set[str] = set()
    plan = []
    for fl in flights:
        placed = None
        for g in gates:
            if g["id"] in used:
                continue
            trial = [(flights[i], next(x for x in world["data"]["gates"] if x["id"] == plan[i])) for i in range(len(plan))]
            trial.append((fl, g))
            if _fits(world, trial):
                placed = g["id"]
                break
        if placed is None:
            return None
        used.add(placed)
        plan.append(placed)
    return tuple(plan)


def greedy_pax(world: dict) -> tuple | None:
    """旅客多的先占人均摆渡更便宜的机位，不计同一波加价。"""
    flights = world["data"]["flights"]
    gates = {g["id"]: g for g in world["data"]["gates"]}
    order = sorted(range(len(flights)), key=lambda i: (-flights[i]["pax"], flights[i]["id"]))
    ranked = sorted(world["data"]["gates"], key=lambda g: (g["bus"], g["remote"], g["id"]))
    chosen: dict[int, str] = {}
    for i in order:
        placed = None
        for g in ranked:
            if g["id"] in chosen.values():
                continue
            pairs = [(flights[j], gates[chosen[j]]) for j in sorted(chosen)]
            pairs.append((flights[i], g))
            if _fits(world, pairs):
                placed = g["id"]
                break
        if placed is None:
            return None
        chosen[i] = placed
    return tuple(chosen[i] for i in range(len(flights)))


def _greedies(world: dict) -> list[tuple]:
    out = [greedy_bridge(world)]
    if "wave" in world["modules"]:
        cheap = greedy_pax(world)
        if cheap:
            out.insert(0, cheap)
    return out


class GateFamily:
    id = "gate"
    primary = "pax_bus"
    shared = "remote_n"
    cf_key = "no_wide"
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
        if not all(len(p) == 2 and p[0] == "G" and p[1].isdigit() for p in plan):
            return None
        return plan

    def plans(self, world: dict) -> Iterator[tuple]:
        ids = [g["id"] for g in world["data"]["gates"]]
        for perm in itertools.permutations(ids):
            yield perm

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        flights = world["data"]["flights"]
        gates = {g["id"]: g for g in world["data"]["gates"]}
        if len(plan) != len(flights) or set(plan) != set(gates):
            return None
        pairs = [(flights[i], gates[plan[i]]) for i in range(len(plan))]
        if not _fits(world, pairs):
            return None
        pax_bus = remote_n = 0
        fired = set()
        if "wide" in world["modules"]:
            fired.add("wide")
        wave = world["modules"].get("wave")
        seen: dict[int, int] = {}
        remotes: list[dict] = []
        for fl, g in pairs:
            if not g["remote"]:
                continue
            remote_n += 1
            remotes.append(fl)
            rate = g["bus"]
            if wave:
                bucket = fl["dep"] // wave["width"]
                if seen.get(bucket, 0):
                    rate += wave["extra"]
                    fired.add("wave")
                seen[bucket] = seen.get(bucket, 0) + 1
            pax_bus += fl["pax"] * rate
        tow = world["modules"].get("tow")
        if tow and remotes:
            fired.add("tow")
            starts: list[int] = []
            sides: list[int] = []
            needs: list[int] = []
            free = [0, 0]
            done: list[int] = []
            for fl in remotes:
                b = 0 if free[0] <= free[1] else 1
                start = max(fl["arr"], free[b])
                starts.append(start)
                sides.append(b)
                needs.append(tow["minutes"])
                done = dual_progress(starts, sides, needs, True)
                free = [0, 0]
                for i, end in enumerate(done):
                    free[sides[i]] = max(free[sides[i]], end)
            for fl, end in zip(remotes, done):
                over = end - fl["dep"]
                if over > 0:
                    pax_bus += fl["pax"] * over
        return Outcome(tuple(plan), {"pax_bus": pax_bus, "remote_n": remote_n}, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        flights = [[f["id"], f["arr"], f["dep"], "宽体" if f["wide"] else "窄体", f["pax"]] for f in d["flights"]]
        gates = [[g["id"], "远机位" if g["remote"] else "靠桥", g["bus"], g["adj"]] for g in d["gates"]]
        return "\n".join([
            "你把这一时段的航班指派到机位。每架航班恰好一个机位，每个机位恰好一架航班。",
            f"航班表按答题顺序排列，每行 `[编号, 到达分钟, 离开分钟, 机型, 旅客数]`：{_c(flights)}。",
            "占用区间含到达分钟、不含离开分钟。同一机位的两段占用不得重叠。",
            f"机位表每行 `[编号, 类型, 人均摆渡分钟, 相邻机位]`：{_c(gates)}。",
            "靠桥机位摆渡分钟为 0。"
            + ("有摆渡波次时，总摆渡分钟按该规则计算。" if "wave" in world["modules"]
               else "总摆渡分钟 = 各航班旅客数 × 该机位人均摆渡分钟，再求和。"),
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        return f"目标：先使{layers[0]}；若仍有多个指派并列，取{layers[1]}者。"

    def questions(self) -> list[dict]:
        return [
            {"name": "plan", "type": "plan", "metric": "pax_bus", "points": 6,
             "text": "按航班表顺序给出机位编号，用短横线连接，例如 G1-G3-G4-G2-G5-G6。"},
            {"name": "pax_bus", "metric": "pax_bus", "points": 5},
            {"name": "remote_n", "metric": "remote_n", "points": 4},
            {"name": "cf_pax_bus", "metric": "pax_bus", "points": 5, "cf": "no_wide"},
        ]


FAMILY = GateFamily()


def pinned_world() -> dict:
    """六架航班同时占用。三架宽体里旅客最多的两架必须占走廊两端，中间只能停窄体。"""
    flights = [
        {"id": "A", "arr": 0, "dep": 60, "wide": True, "pax": 50},
        {"id": "B", "arr": 0, "dep": 60, "wide": True, "pax": 200},
        {"id": "C", "arr": 0, "dep": 60, "wide": True, "pax": 180},
        {"id": "D", "arr": 0, "dep": 60, "wide": False, "pax": 40},
        {"id": "E", "arr": 0, "dep": 60, "wide": False, "pax": 30},
        {"id": "F", "arr": 0, "dep": 60, "wide": False, "pax": 20},
    ]
    gates = [
        {"id": "G1", "remote": False, "bus": 0, "adj": ["G2"]},
        {"id": "G2", "remote": False, "bus": 0, "adj": ["G1", "G3"]},
        {"id": "G3", "remote": False, "bus": 0, "adj": ["G2"]},
        {"id": "G4", "remote": True, "bus": 10, "adj": []},
        {"id": "G5", "remote": True, "bus": 10, "adj": []},
        {"id": "G6", "remote": True, "bus": 10, "adj": []},
    ]
    return {
        "family": "gate",
        "data": {"flights": flights, "gates": gates},
        "modules": {"wide": {}},
        "objective": ["pax_bus", "remote_n"],
        "questions": FAMILY.questions(),
        "background": [],
    }
