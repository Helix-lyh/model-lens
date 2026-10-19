"""旧配送实例（reasoning_gen NX-12/18）与 worldkit 世界的双向转换，只用于复现验收与第三方对照。"""
from __future__ import annotations

import copy

_QUESTIONS = {
    "NX-12": [("total", "total", 6), ("late_n", "late_n", 4), ("walk", "walk", 4)],
    "NX-18": [("late_n", "late_n", 6), ("total", "total", 4), ("walk", "walk", 4)],
}
# 旧版删除测试未列入的模块（在题面中、不参与删除测试）
_BACKGROUND = {
    "NX-12": ["outage", "closed", "flood", "return_w"],
    "NX-18": ["outage", "closed", "flood", "down", "mutex"],
}
# 旧条件名 → 新条件名
CONDITION_NAMES = {"ready": "出餐时刻"}


def world_from_nx(item_id: str, inst: dict) -> dict:
    mods: dict = {
        "outage": {"spans": copy.deepcopy(inst["outages"])},
        "register": {"minutes": dict(inst["register"])},
        "closed": {"spans": copy.deepcopy(inst["closed"])},
        "down": {"rate": inst.get("down_rate", 1)},
        "congestion": {"from": inst["congestion_from"], "mult": inst["congestion_mult"]},
        "carry": {"max": inst["max_carry"]},
        "cancel": {"ids": list(inst["cancel_ids"])},
        "flood": {"t": inst["flood"][0], "building": inst["flood"][1],
                  "scope": "deliver" if inst.get("flood_deliver") else "enter"},
        "mutex": {},
    }
    if inst.get("early_return"):
        mods["return_w"] = {}
    if any("ready" in o for o in inst["orders"].values()):
        mods["ready"] = {}
    if inst.get("cold_limit") is not None:
        mods["cold"] = {"limit": inst["cold_limit"]}
    qs = [{"name": n, "metric": m, "points": p} for n, m, p in _QUESTIONS[item_id]]
    qs.append({"name": "cf_total", "metric": "total", "points": 6, "cf": "swap_shock"})
    return {
        "family": "delivery",
        "data": {"roads": dict(inst["roads"]), "orders": copy.deepcopy(inst["orders"]),
                 "role": "冷藏骑手" if "cold" in mods else "骑手"},
        "modules": mods,
        "objective": (["late_n"] if inst.get("late_first", True) else []) + ["total", "walk"],
        "objective_conditions": {"late_n": "先少迟到"} if inst.get("late_first", True) else {},
        "questions": qs,
        "background": [b for b in _BACKGROUND[item_id] if b in mods],
    }


def nx_from_world(world: dict) -> dict:
    """世界 → 旧求解器实例；缺失的模块取中性值。"""
    m = world["modules"]
    orders = copy.deepcopy(world["data"]["orders"])
    if "ready" not in m:
        for o in orders.values():
            o["ready"] = 0
    buildings = sorted({o["building"] for o in orders.values()})
    return {
        "roads": dict(world["data"]["roads"]),
        "outages": {b: (m.get("outage") or {}).get("spans", {}).get(b, []) for b in buildings},
        "orders": orders,
        "down_rate": m["down"]["rate"] if "down" in m else 0,
        "register": dict(m["register"]["minutes"]) if "register" in m else {},
        "late_first": "late_n" in world["objective"],
        "congestion_from": m["congestion"]["from"] if "congestion" in m else 10**9,
        "congestion_mult": m["congestion"]["mult"] if "congestion" in m else 1,
        "max_carry": m["carry"]["max"] if "carry" in m else 99,
        "cold_limit": m["cold"]["limit"] if "cold" in m else None,
        "closed": copy.deepcopy(m["closed"]["spans"]) if "closed" in m else {},
        "cancel_ids": list(m["cancel"]["ids"]) if "cancel" in m else [],
        "flood": [m["flood"]["t"], m["flood"]["building"]] if "flood" in m else [10**9, None],
        "detour": 0,
        "early_return": "return_w" in m,
        "flood_deliver": "flood" in m and m["flood"].get("scope", "deliver") == "deliver",
        "force_both_shocks": "mutex" not in m,
    }
