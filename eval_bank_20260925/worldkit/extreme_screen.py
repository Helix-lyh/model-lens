"""极难筛：贪心路只做对 4 分那一问，另外三问都错。

不看因子个数。一单若单独配送都已经迟到，迟到集合不用搜就能读出来，这种题丢掉。
"""
from __future__ import annotations

from eval_bank_20260925.worldkit.families import delivery

FAM = delivery.FAMILY


def late_ids(out) -> set[str]:
    return set(out.trace[1])


def repair_windows(world: dict, rng) -> bool:
    """把截止改到「单独去能准时、排到最后会迟到」之间。到达时刻与截止无关，改完不用重跑。"""
    live = FAM.effective(world)
    active = FAM.active_orders(live)
    chosen = {}
    for oid in active:
        solo = FAM.simulate(live, (oid,))
        rest = tuple(x for x in active if x != oid)
        last = FAM.simulate(live, rest + (oid,))
        if solo is None or last is None:
            return False
        solo_at = dict(solo.trace[0])[oid]
        last_at = dict(last.trace[0])[oid]
        if last_at <= solo_at:
            return False
        span = last_at - solo_at
        hi = solo_at + max(1, span // 3)
        chosen[oid] = int(rng.randint(solo_at, min(hi, last_at - 1)))
    for oid, dl in chosen.items():
        world["data"]["orders"][oid]["deadline"] = dl
    return True


def solo_late_orders(world: dict) -> list[str]:
    """单独从站点出发仍赶不上截止的订单。这种单不算路线也能判定必迟。"""
    live = FAM.effective(world)
    forced = []
    for oid in FAM.active_orders(live):
        out = FAM.simulate(live, (oid,))
        if out is None or oid in late_ids(out):
            forced.append(oid)
    return forced


def always_on_time(world: dict) -> list[str]:
    """排到最后一单仍然准时的订单。它不参与迟到取舍。"""
    live = FAM.effective(world)
    active = FAM.active_orders(live)
    stuck = []
    for oid in active:
        rest = tuple(x for x in active if x != oid)
        out = FAM.simulate(live, rest + (oid,))
        if out is not None and oid not in late_ids(out):
            stuck.append(oid)
    return stuck


def salient_orders(world: dict) -> list[tuple[str, tuple]]:
    """模型会先写的两种顺序：按截止，或先赶正在封闭的楼。不含回站记号，回站由连续配送上限在模拟里插入。"""
    live = FAM.effective(world)
    active = FAM.active_orders(live)
    orders = world["data"]["orders"]
    by_due = tuple(sorted(active, key=lambda oid: (orders[oid]["deadline"], oid)))
    closed = set((live["modules"].get("closed") or {}).get("spans") or {})
    rush = tuple(oid for oid in by_due if orders[oid]["building"] in closed)
    rush += tuple(oid for oid in by_due if oid not in rush)
    out = [("先送截止更早的单", by_due)]
    if rush != by_due:
        out.append(("先赶封闭的楼", rush))
    return out


def other_late_set(world: dict, best_plan: tuple, best_late: set[str], best_n: int) -> bool:
    """交换最优顺序里的两单后，迟到单数不变、迟到的是哪些单变了。"""
    ids = [p for p in best_plan if p != "W"]
    live = FAM.effective(world)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            alt = ids[:]
            alt[i], alt[j] = alt[j], alt[i]
            out = FAM.simulate(live, tuple(alt))
            if out is None or out.metrics["late_n"] != best_n:
                continue
            if late_ids(out) != best_late:
                return True
    return False


def trap_row(world: dict, best: dict) -> dict | None:
    """找到一条贪心：顺序不同，迟到单数相同但迟到集合不同，送达时刻不同。"""
    best_plan = tuple(p for p in best["plan"] if p != "W")
    best_late = set(best["late"])
    best_n = int(best["late_n"])
    best_total = int(best["total"])
    live = FAM.effective(world)
    for name, plan in salient_orders(world):
        out = FAM.simulate(live, plan)
        if out is None or tuple(p for p in out.plan if p != "W") == best_plan:
            continue
        if out.metrics["late_n"] != best_n or out.metrics["total"] == best_total:
            continue
        if late_ids(out) == best_late:
            continue
        return {"name": name, "plan": plan, "total": out.metrics["total"], "late_n": best_n, "late": sorted(late_ids(out))}
    return None
