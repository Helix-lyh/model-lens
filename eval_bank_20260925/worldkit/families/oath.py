"""誓言清算台：登记满若干步才生效，执行收成本，超额改记罚没，余额不足则整笔拒绝。"""
from __future__ import annotations

import copy
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome

DECISIONS = ("按日志结算",)


def _c(value) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _t_delay(p, _w):
    return (f"滞后生效：一份誓言在步骤 t 登记，从步骤 t+{p['k']} 起（含这一步）才有效。"
            "有效之前执行，整笔拒绝。口头未登记的誓言始终无效。")


def _t_cost(p, _w):
    return f"执行成本：一次成功执行，转出方在面额之外再扣 {p['fee']} 个信用单位。拒绝执行不扣成本。"


def _t_cap(p, _w):
    return (f"持有上限：任一方有效持有不得超过 {p['n']}。"
            "转入后若超过上限，超过的部分不入账，改记到罚没合计。")


def _t_fine(p, _w):
    return (f"整笔拒绝：转出方面额加成本仍不足时，余额不动，罚没合计加 {p['m']}。"
            "不足也不能部分成交。")


def _t_habit(_p, _w):
    return ("无编号习惯（干扰，不得执行）：有人认为登记即过户、可以部分成交、没有持有上限。"
            "本题只执行上面有编号的四条。")


MODULES = {m.id: m for m in [
    Module("delay", "滞后生效", 10, _t_delay),
    Module("cost", "执行成本", 20, _t_cost),
    Module("cap", "持有上限", 30, _t_cap),
    Module("fine", "整笔拒绝", 40, _t_fine),
    Module("habit", "无编号习惯", 90, _t_habit),
]}

METRICS = {
    "live_b_mid": "中段时 B 的有效持有",
    "live_b": "结束时 B 的有效持有",
    "penalty": "罚没合计",
}

OBJECTIVE_PHRASES = {
    "live_b": "按日志结算（没有可选方案）",
}


def _delay_plus(world: dict) -> dict:
    x = copy.deepcopy(world)
    d = x["modules"]["delay"]
    x["modules"]["delay"] = {**d, "k": d["k"] + 1}
    return x


COUNTERFACTUALS = {
    "delay_plus": Counterfactual(_delay_plus, lambda w: f"若滞后改为 {w['modules']['delay']['k'] + 1} 步才生效（其余不变），"),
}

READINGS: dict = {}


def _opening(world: dict) -> dict[str, int]:
    return {p: world["data"]["opening"][p] for p in world["data"]["parties"]}


def _replay(world: dict, *, earth: bool = False) -> dict[str, int]:
    oaths = {o["id"]: dict(o) for o in world["data"]["oaths"]}
    live = _opening(world)
    penalty = 0
    registered_at: dict[str, int] = {}
    k = 0 if earth else world["modules"]["delay"]["k"]
    fee = 0 if earth else world["modules"]["cost"]["fee"]
    cap = 10**9 if earth else world["modules"]["cap"]["n"]
    fine = 0 if earth else world["modules"]["fine"]["m"]
    mid_at = world["data"]["mid_at"]
    live_b_mid = 0
    for i, ev in enumerate(world["data"]["log"]):
        op = ev["op"]
        if op == "reg":
            registered_at[ev["oath"]] = i
            if earth:
                oid = ev["oath"]
                spec = oaths[oid]
                src, dst, amt = spec["src"], spec["dst"], spec["units"]
                take = min(live[src], amt) if earth else amt
                live[src] -= take
                live[dst] += take
        elif op == "run" and not earth:
            oid = ev["oath"]
            spec = oaths[oid]
            src, dst, amt = spec["src"], spec["dst"], spec["units"]
            ready = oid in registered_at and i >= registered_at[oid] + k
            if not ready or live[src] < amt + fee:
                penalty += fine
            else:
                live[src] -= amt + fee
                live[dst] += amt
                extra = live[dst] - cap
                if extra > 0:
                    live[dst] = cap
                    penalty += extra
        if i == mid_at:
            live_b_mid = live["B"]
    if mid_at >= len(world["data"]["log"]):
        live_b_mid = live["B"]
    return {"live_b_mid": live_b_mid, "live_b": live["B"], "penalty": penalty}


class OathFamily:
    id = "oath"
    primary = "live_b"
    shared = "penalty"
    cf_key = "delay_plus"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS

    def effective(self, world: dict) -> dict:
        return world

    def normalize_plan(self, plan: tuple) -> tuple | None:
        return plan if plan == ("LOG",) else None

    def plans(self, world: dict) -> Iterator[tuple]:
        yield ("LOG",)

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        if plan != ("LOG",):
            return None
        m = _replay(world, earth=False)
        fired = {k for k in ("delay", "cost", "cap", "fine") if k in world["modules"]}
        return Outcome(("LOG",), m, [], frozenset(fired))

    def header(self, world: dict) -> str:
        d = world["data"]
        oaths = [[o["id"], o["src"], o["dst"], o["units"]] for o in d["oaths"]]
        opening = [[p, d["opening"][p]] for p in d["parties"]]
        log = []
        for i, ev in enumerate(d["log"]):
            if ev["op"] == "reg":
                log.append([i, "登记", ev["oath"]])
            elif ev["op"] == "run":
                log.append([i, "执行", ev["oath"]])
            else:
                log.append([i, "空步", "-"])
        return "\n".join([
            "你是清算台书记。没有可选方案，只按日志顺序结算。口头未登记的誓言无效。",
            f"各方期初有效持有每行 `[方, 单位]`：{_c(opening)}。",
            f"誓言表每行 `[编号, 转出方, 转入方, 面额]`：{_c(oaths)}。",
            f"日志每行 `[步骤, 动作, 誓言编号]`：{_c(log)}。步骤从 0 连续编号。",
            f"中段问的是步骤 {d['mid_at']} 结算完毕后 B 的有效持有。",
        ])

    def objective_text(self, world: dict) -> str:
        return "目标：按日志结算，不要改顺序、不要补登记。"

    def questions(self) -> list[dict]:
        return [
            {"name": "mid", "metric": "live_b_mid", "points": 5,
             "text": "中段时 B 的有效持有是多少？"},
            {"name": "end", "metric": "live_b", "points": 5,
             "text": "结束时 B 的有效持有是多少？"},
            {"name": "pen", "metric": "penalty", "points": 5,
             "text": "罚没合计是多少？"},
            {"name": "cf_end", "metric": "live_b", "points": 5, "cf": "delay_plus"},
        ]


FAMILY = OathFamily()
