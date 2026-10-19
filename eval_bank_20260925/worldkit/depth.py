"""困难 / 极难的深度筛：蝴蝶效应、陷阱、同形干扰。不增加订单、楼宇或模块种类。

思考时长不是通过条件。陷阱是规则允许的一条贪心走法，和最优顺序不同。
同形干扰是写在题面里、删掉不改变所问答案、收紧一个参数就会改变顺序或迟到集合的冷链时限。
"""
from __future__ import annotations

import copy

from eval_bank_20260925.worldkit.families import delivery


def deadline_plan(world: dict) -> tuple:
    """先送截止更早的单；连续送满上限就回站。这是一条不搜索的贪心路线。"""
    cancelled = set((world["modules"].get("cancel") or {}).get("ids", []))
    orders = [oid for oid in world["data"]["orders"] if oid not in cancelled]
    orders.sort(key=lambda oid: (world["data"]["orders"][oid]["deadline"], oid))
    cap = (world["modules"].get("carry") or {}).get("max")
    plan: list[str] = []
    run = 0
    for oid in orders:
        if cap and run >= cap:
            plan.append("W")
            run = 0
        plan.append(oid)
        run += 1
    return tuple(plan)


def prepare(world: dict, solve) -> dict | None:
    """把冷链时限放到最优路线刚好不触发的位置，并记入背景。返回 None 表示基线解不出来。"""
    if "cold" not in world["modules"]:
        return world
    w = copy.deepcopy(world)
    for _ in range(4):
        st = solve(w)
        if not _solved(st):
            return None
        need = _inert_limit(w, st)
        if need is None:
            return w
        if w["modules"]["cold"]["limit"] == need and "cold" in w.get("background", []):
            return w
        w["modules"]["cold"]["limit"] = need
        if "cold" not in w["background"]:
            w["background"] = [*w.get("background", []), "cold"]
    return w


def assess(world: dict, tier: dict, solve) -> dict:
    """深度档位：order 要求陷阱只改顺序、迟到单数不变；late 要求顺序和迟到单数一起变。"""
    base = solve(world)
    if not _solved(base):
        return {"ok": False, "reason": "depth:prepare"}
    butterfly = _butterfly(world, base, solve)
    trap = _trap(world, base, solve, tier.get("depth"))
    distractor = _distractor(world, base, solve)
    reason = ""
    if butterfly is None:
        reason = "depth:butterfly"
    elif trap is None:
        reason = "depth:trap"
    elif distractor is None:
        reason = "depth:distractor"
    return {
        "ok": reason == "",
        "reason": reason,
        "butterfly": butterfly,
        "trap": trap,
        "distractor": distractor,
    }


def _butterfly(world: dict, base: dict, solve) -> str | None:
    base_fired = set(base.get("fired") or [])
    base_plan = tuple(base["plan"])
    base_late = tuple(base.get("late") or [])
    for desc, alt in delivery.perturbations(world):
        st = solve(alt)
        if not _solved(st):
            continue
        order_changed = tuple(st["plan"]) != base_plan
        late_changed = tuple(st.get("late") or []) != base_late
        if not order_changed and not late_changed:
            continue
        target = _touched(world, alt)
        others = (base_fired ^ set(st.get("fired") or [])) - target
        if others:
            return desc
    return None


def _trap(world: dict, base: dict, solve, kind: str) -> str | None:
    """order：贪心路线顺序不同，迟到单数最多差 1。late：迟到单数至少差 2。"""
    for name, plan in _candidates(world, solve):
        judged = _replay(world, plan)
        if judged is None or judged[0] == tuple(base["plan"]):
            continue
        delta = abs(judged[1] - int(base["late_n"]))
        if kind == "late" and delta >= 2:
            return name
        if kind != "late" and delta <= 1:
            return name
    return None


def _candidates(world: dict, solve) -> list[tuple[str, tuple]]:
    out = [("先送更紧的单", deadline_plan(world))]
    idle = _idle_shock(world)
    if idle is not None:
        alt = copy.deepcopy(world)
        active = "closed" if idle == "flood" else "flood"
        alt["modules"].pop(active, None)
        alt["modules"].pop("mutex", None)
        alt["background"] = [b for b in alt.get("background", []) if b not in (idle, active, "mutex")]
        st = solve(alt)
        if _solved(st):
            out.append((f"按未生效的{idle}来排", tuple(st["plan"])))
    if "congestion" in world["modules"]:
        alt = copy.deepcopy(world)
        alt["modules"].pop("congestion", None)
        st = solve(alt)
        if _solved(st):
            out.append(("无视拥堵阈值", tuple(st["plan"])))
    return out


def _distractor(world: dict, base: dict, solve) -> str | None:
    if "cold" not in world["modules"] or "cold" not in world.get("background", []):
        return None
    gone = copy.deepcopy(world)
    gone["modules"].pop("cold")
    gone["background"] = [b for b in gone["background"] if b != "cold"]
    st = solve(gone)
    if not _same_decision(base, st):
        return None
    limit = world["modules"]["cold"]["limit"]
    for tighter in (max(1, limit - 2), max(1, limit // 2), 1):
        if tighter >= limit:
            continue
        alt = copy.deepcopy(world)
        alt["modules"]["cold"]["limit"] = tighter
        st = solve(alt)
        if _solved(st) and (tuple(st["plan"]) != tuple(base["plan"]) or tuple(st.get("late") or []) != tuple(base.get("late") or [])):
            return f"冷链时限收到 {tighter} 分钟会改变决策"
    return None


def _replay(world: dict, plan: tuple) -> tuple[tuple, int] | None:
    out = delivery.FAMILY.simulate(delivery.FAMILY.effective(world), plan)
    if out is None:
        return None
    return tuple(out.plan), int(out.metrics["late_n"])


def _inert_limit(world: dict, st: dict) -> int | None:
    arrivals = st.get("arrivals") or {}
    slack = []
    for oid, o in world["data"]["orders"].items():
        if oid not in arrivals:
            continue
        if int(arrivals[oid]) <= o["deadline"]:
            slack.append(int(arrivals[oid]) - int(o.get("ready", 0)))
    if not slack:
        return None
    return max(slack) + 1


def _idle_shock(world: dict) -> str | None:
    bg = set(world.get("background") or [])
    for mid in ("flood", "closed"):
        if mid in bg and mid in world["modules"] and "mutex" in world["modules"]:
            other = "closed" if mid == "flood" else "flood"
            if other in world["modules"]:
                return mid
    return None


def _touched(base: dict, alt: dict) -> set[str]:
    keys = set(base["modules"]) | set(alt["modules"])
    return {k for k in keys if base["modules"].get(k) != alt["modules"].get(k)}


def _same_decision(base: dict, st: dict) -> bool:
    if not _solved(st):
        return False
    return (tuple(st["plan"]) == tuple(base["plan"]) and tuple(st.get("late") or []) == tuple(base.get("late") or [])
            and int(st["total"]) == int(base["total"]))


def _solved(st: dict | None) -> bool:
    return bool(st) and not st.get("error") and st.get("status") == "ok" and bool(st.get("plan"))
