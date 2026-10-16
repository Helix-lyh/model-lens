"""20261020 网状交互加难：NX-12/14/16/17/18 的冻结实例、求解器与度数报告。

交互定义（联合承重）：A 与 B 交互当且仅当
  key(del A)≠key(base) ∧ key(del B)≠key(base)
  ∧ key(del A∘B)≠key(del A) ∧ key(del A∘B)≠key(del B)
（删 A 后 B 仍承重，删 B 后 A 仍承重）。度数 = 交互邻居数，要求 ≥3。
删除测试只看主判分数值（非 cf_*）。
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Callable

PACK = json.loads(Path(__file__).with_name("reasoning_mesh_pack_20261020.json").read_text(encoding="utf-8"))


def main_key_names(keys_spec) -> list[str]:
    return [n for n, *_ in keys_spec if not n.startswith("cf_")]


def interacts(base: dict, ka: dict, kb: dict, kab: dict, names: list[str]) -> bool:
    def vec(d):
        return tuple(d[k] for k in names)

    b, a, bb, ab = vec(base), vec(ka), vec(kb), vec(kab)
    return a != b and bb != b and ab != a and ab != bb


# ---------------------------------------------------------------------------
# NX-16：shelf≥3 + 滚动批量窗口，跨天 DP
# ---------------------------------------------------------------------------

def plan_nx16(inst: dict) -> tuple[dict, int]:
    days, cap, box, shelf = inst["days"], inst["capacity"], inst["box"], inst["shelf"]
    hot_rule, lead = inst["hot_rule"], inst.get("lead", 1)
    bulk_at = inst.get("bulk_at", 10**9)
    bulk_off = inst.get("bulk_off", 0)
    roll_w = inst.get("bulk_window", 1)
    wmult = inst.get("weekend_mult", 1)
    fee = inst["delivery_fee"]
    n = len(days)
    memo: dict = {}

    def ucost(d, recent):
        return max(1, d["cost"] - (bulk_off if sum(recent) >= bulk_at else 0))

    def best(i, carry, recent):
        if i == n:
            return 0, 1, []
        key = (i, carry, recent)
        if key in memo:
            return memo[key]
        d = days[i]
        hot = d["kind"] == "hot" and hot_rule
        price = d["price"] * (wmult if (i % 7) >= 5 else 1)
        blocked = i in inst.get("supplier_out", [])
        top = count = plan = None
        room = cap - sum(carry)
        buys = [0] if (hot or blocked) else list(range(0, max(0, room) + 1, box))
        for buy in buys:
            demand = d["demand"]
            left = list(carry)
            sold = 0
            for a in range(len(left)):
                take = min(left[a], demand - sold)
                left[a] -= take
                sold += take
            if lead == 0:
                take = min(buy, demand - sold)
                buy_left = buy - take
                sold += take
            else:
                buy_left = buy
            waste = left[0] if left else 0
            nxt_list = (left[1:] if left else []) + [buy_left]
            while len(nxt_list) < shelf:
                nxt_list.append(0)
            nxt_list = nxt_list[:shelf]
            if hot or i == n - 1:
                waste = waste + sum(nxt_list)
                nxt = tuple(0 for _ in range(shelf))
            else:
                nxt = tuple(nxt_list)
            if sum(nxt) > cap:
                continue
            recent2 = (recent + (buy,))[-roll_w:]
            gain = sold * price - buy * ucost(d, recent2) - (fee if buy else 0)
            sub, sc, sp = best(i + 1, nxt, recent2)
            total = gain + sub
            row = (buy, sold, waste)
            if top is None or total > top:
                top, count, plan = total, sc, [row] + sp
            elif total == top:
                count += sc
        memo[key] = (top, count, plan)
        return memo[key]

    init = tuple(0 for _ in range(shelf))
    profit, count, plan = best(0, init, tuple())
    if not plan:
        return {"buy": [], "sold": [], "waste": [], "profit": -10**9}, 0
    return {
        "buy": [p[0] for p in plan],
        "sold": [p[1] for p in plan],
        "waste": [p[2] for p in plan],
        "profit": profit,
    }, count


def gen_nx16(_rng):
    return copy.deepcopy(PACK["NX-16"])


def solve_nx16(inst):
    return plan_nx16(inst)[0]


def extra_nx16(inst, ans):
    if plan_nx16(inst)[1] != 1 or sum(ans["waste"]) < 1:
        return False
    loose = dict(inst, box=1, hot_rule=False, shelf=99, delivery_fee=0, lead=0, bulk_at=10**9, weekend_mult=1, supplier_out=[], bulk_window=1)
    return solve_nx16(loose)["buy"] != ans["buy"]


def prompt_nx16(inst):
    from eval_bank_20260925.reasoning_gen import _compact

    rows = [[i + 1, d["kind"], d["demand"], d["price"], d["cost"]] for i, d in enumerate(inst["days"])]
    n = len(inst["days"])
    weekend = "、".join(str(i + 1) for i in range(n) if i % 7 >= 5)
    out_days = "、".join(str(i + 1) for i in inst["supplier_out"])
    return f"""
水果店连续经营 {n} 天，库容 {inst["capacity"]}。每天表每行 `[第几天, 天气(normal/hot), 需求, 售价, 进价]`（天数从 1 开始）：{_compact(rows)}。
规则：
- 每天开门前可进货，进货量必须是 {inst["box"]} 的整数倍（可以为 0），单日进货后「在库+本日新进」不超过库容 {inst["capacity"]}；hot 天不能进货。
- 当天进的货要到次日开门才能上架；上架后可连续销售至多 {inst["shelf"]} 天（含上架当日），按先进先出；超期未售出的在当天结束时报废。
- 当天销量 = min(需求, 当天可售库存)，不能惜售。hot 天结束时剩余库存全部报废。最后一天结束时剩余库存全部报废。
- 进货量大于 0 的天另付运费 {inst["delivery_fee"]}。
- 近 {inst["bulk_window"]} 个进货日（含当天）的进货量累计 ≥ {inst["bulk_at"]} 时，当天进价每件减 {inst["bulk_off"]}（不低于 1）。
- 第 {weekend} 天是周末，当天售价×{inst["weekend_mult"]}。
- 供应商停供日（当天不能进货）：第 {out_days} 天。
- 利润 = 各天（销量×当日售价 − 进货量×实际进价 − 运费）之和。目标：利润最大。
输出 JSON 对象，只含以下字段：
- `buy`：长度 {n} 的整数数组，每天进货量。
- `sold`：长度 {n} 的整数数组，每天销量。
- `waste`：长度 {n} 的整数数组，每天结束时报废量。
- `profit`：整数，最大利润。"""


# ---------------------------------------------------------------------------
# NX-14：有效优先级并列时分支，取总费用最优
# ---------------------------------------------------------------------------

def _rate(tariff, m):
    for a, b, p in tariff:
        if a <= m < b:
            return p
    return tariff[-1][2]


def solve_nx14(inst: dict) -> dict:
    cars = {c: {"arrive": a, "energy": e, "prio": p} for c, a, e, p in inst["cars"]}
    piles = inst["piles"]
    aging, aging_cap = inst["aging"], inst.get("aging_cap", 10**9)
    max_wait = inst.get("max_wait", 10**9)
    peak_a, peak_b = inst["peak"]
    peak_ban = inst.get("peak_ban", {})
    aging_off = inst.get("aging_off_after")
    min_prio = inst.get("min_prio", {})
    pile_down = inst.get("pile_down", {})

    def eff(c, t):
        if not aging or aging_cap <= 0:
            return cars[c]["prio"]
        te = t if aging_off is None else min(t, aging_off)
        return cars[c]["prio"] + max(0, min((te - cars[c]["arrive"]) // aging, aging_cap))

    def pile_blocked(pile, t):
        if peak_ban.get(pile) and peak_a <= t < peak_b:
            return True
        return any(a <= t < b for a, b in pile_down.get(pile, []))

    best = None
    scored_opts: set = set()

    def future_times(t, pending, free_at):
        fut = [cars[c]["arrive"] for c in pending if cars[c]["arrive"] > t]
        fut += [v for v in free_at.values() if v > t]
        fut += [cars[c]["arrive"] + max_wait + 1 for c in pending if cars[c]["arrive"] <= t]
        for spans in pile_down.values():
            for a, b in spans:
                if t < a:
                    fut.append(a)
                if t < b:
                    fut.append(b)
        if aging_off is not None and t < aging_off:
            fut.append(aging_off)
        fut += [peak_a, peak_b]
        if aging and aging_cap > 0:
            for c in pending:
                arr = cars[c]["arrive"]
                if arr <= t:
                    for k in range(1, aging_cap + 1):
                        ft = arr + k * aging
                        if aging_off is not None:
                            ft = min(ft, aging_off)
                        if ft > t:
                            fut.append(ft)
        return [v for v in fut if v > t]

    def finish(sched):
        nonlocal best, scored_opts
        a, b = inst["peak"]
        peak_cost = sum(_rate(inst["tariff"], m) for _c, _p, s, e, _x in sched for m in range(s, e) if a <= m < b)
        total = sum(r[4] for r in sched)
        key = (-len(sched), total, peak_cost)
        ans = {
            "schedule": sorted(sched, key=lambda r: (r[2], r[1])),
            "peak_cost": peak_cost,
            "total_cost": total,
            "finish_order": [r[0] for r in sorted(sched, key=lambda r: (r[3], r[0]))],
        }
        if best is None or key < best[0]:
            best = (key, ans)
            scored_opts = {(total, peak_cost)}
        elif key == best[0]:
            scored_opts.add((total, peak_cost))

    def dfs(t, pending, free_at, sched):
        pending = {c for c in pending if not (cars[c]["arrive"] <= t and t - cars[c]["arrive"] > max_wait)}
        if not pending:
            finish(sched)
            return

        def assign_from(pile_idx, pending, free_at, sched, t):
            if pile_idx >= len(piles):
                fut = future_times(t, pending, free_at)
                if not fut:
                    finish(sched)
                    return
                dfs(min(fut), pending, free_at, sched)
                return
            pile = sorted(piles)[pile_idx]
            if free_at[pile] > t or pile_blocked(pile, t):
                assign_from(pile_idx + 1, pending, free_at, sched, t)
                return
            ready = [c for c in pending if cars[c]["arrive"] <= t and cars[c]["prio"] >= min_prio.get(pile, 0)]
            if not ready:
                assign_from(pile_idx + 1, pending, free_at, sched, t)
                return
            mx = max(eff(c, t) for c in ready)
            cands = sorted(c for c in ready if eff(c, t) == mx)
            for c in cands:
                end = t + math.ceil(cars[c]["energy"] / piles[pile])
                cost = sum(_rate(inst["tariff"], m) for m in range(t, end))
                assign_from(pile_idx + 1, pending - {c}, {**free_at, pile: end}, sched + [[c, pile, t, end, cost]], t)

        can = any(
            free_at[p] <= t
            and not pile_blocked(p, t)
            and any(cars[c]["arrive"] <= t and cars[c]["prio"] >= min_prio.get(p, 0) for c in pending)
            for p in piles
        )
        if can:
            assign_from(0, pending, free_at, sched, t)
        else:
            fut = future_times(t, pending, free_at)
            if fut:
                dfs(min(fut), pending, free_at, sched)
            else:
                finish(sched)

    dfs(0, set(cars), {p: 0 for p in piles}, [])
    return best[1]


def gen_nx14(_rng):
    return copy.deepcopy(PACK["NX-14"])


def extra_nx14(inst, ans):
    arrive = {c: a for c, a, _e, _p in inst["cars"]}
    left = len(inst["cars"]) - len(ans["schedule"])
    return sum(1 for r in ans["schedule"] if r[2] > arrive[r[0]]) >= 1 and ans["peak_cost"] > 0 and left >= 0 and len(ans["schedule"]) >= 5


def prompt_nx14(inst):
    from eval_bank_20260925.reasoning_gen import _compact

    piles = ", ".join(f"{k} 功率 {v}" for k, v in inst["piles"].items())
    a, b = inst["peak"]
    off = inst["aging_off_after"]
    return f"""
充电桩：{piles}，0 分钟全部空闲。电价表每项 `[开始, 结束, 每分钟价格]`（半开区间）：{_compact(inst["tariff"])}。
车辆表每行 `[id, 到达, 电量, 初始priority]`：{_compact(inst["cars"])}。
约束：
- 车辆在桩上充电时长为 `ceil(电量/功率)` 分钟，开始后不可中断、不可换桩；同一桩同一时刻最多一辆车。
- 桩的准入（初始priority 低于该值的车辆不能使用该桩）：{_compact(inst["min_prio"])}；未列出的桩无要求。
- 峰时 [{inst["peak"][0]},{inst["peak"][1]}) 不能开始新充电的桩（已开始的充电照常做完）：{_compact([k for k, v in inst["peak_ban"].items() if v])}。
- 等待超过 {inst["max_wait"]} 分钟仍未开始则离开。
- 桩突发停用（半开，停用期间不能开始新充电，已开始的照常做完）：{_compact(inst["pile_down"])}。
- 桩不得闲置：任一时刻若某桩空闲、未被禁用，且有已到达未开始、可使用该桩的车辆，该时刻必须开始充电。
- 车辆在时刻 t 的有效 priority = 初始priority + max(0, min(floor((min(t, {off}) − 到达) / {inst["aging"]}), {inst["aging_cap"]}))；即从第 {off} 分钟起等待不再增加有效 priority，此前已获得的加成保留。
- 接车时只在有效 priority 最大的已到达可服务车辆中选择；若并列多人，则在所有并列选择（含多空闲桩的分配）中取使「已充电车辆费用总和」最小的方案，总和相同时再取峰时费用较小者；再相同则按开始时刻、桩号、车辆 id 的字典序。
- 费用 = 充电各分钟所在时段价格之和，与功率无关。
输出 JSON 对象，只含以下字段：
- `schedule`：数组，每项 `[id, 桩, 开始, 结束, 费用]`，按开始、桩编号升序。
- `peak_cost`：整数，所有车辆落在 [{a},{b}) 内各分钟的费用之和。
- `finish_order`：数组，车辆 id 按结束时刻升序，同刻按 id。"""




# ---------------------------------------------------------------------------
# NX-12 / NX-18：洪涝后移 + late_first 承重（复用 reasoning_gen 配送引擎）
# ---------------------------------------------------------------------------

def gen_nx12(_rng):
    return copy.deepcopy(PACK["NX-12"])


def solve_nx12(inst):
    from eval_bank_20260925 import reasoning_gen as g
    live = g._apply_mutex_delivery(inst)
    key = (lambda late, total: (len(late), total)) if inst.get("late_first", True) else (lambda late, total: (total,))
    best = g._ranked(live, key)[0]
    cf = g._ranked(g._apply_mutex_delivery(g._other_shock(inst, live, g.PRIO_DELIVERY)), key)[0]
    return {
        "route": best[1], "arrivals": best[2], "late": best[3], "total": best[4],
        "cf_total": best[4] if inst.get("cf_equals_factual") else cf[4],
    }


def extra_nx12(inst, ans):
    from eval_bank_20260925 import reasoning_gen as g
    live = g._apply_mutex_delivery(inst)
    key = (lambda late, total: (len(late), total)) if inst.get("late_first", True) else (lambda late, total: (total,))
    rows = g._ranked(live, key)
    return g._values_unique(rows, lambda r: (r[4], len(r[3]))) and len(ans["arrivals"]) >= 4


def prompt_nx12(inst):
    from eval_bank_20260925.reasoning_gen import _compact, _city_rows
    orders = [[oid, o["building"], o["floor"], o["deadline"]] for oid, o in sorted(inst["orders"].items())]
    return f"""
骑手 0 分钟在站点 W（地面），完成全部订单，顺序自选。任意两地点之间道路双向可走，行驶分钟表每行 `[地点, 地点, 分钟]`：{_compact(_city_rows(inst))}。
订单表每行 `[id, 楼宇, 楼层, deadline]`，订单均在 0 分钟可配送：{_compact(orders)}。
电梯停运区间（半开区间 [开始, 结束)）：{_compact(inst["outages"])}。
首次进入楼宇需在地面登记（分钟，同一楼宇再次进入不再登记）：{_compact(inst["register"])}。
楼宇封闭区间（半开）：{_compact(inst["closed"])}。从时刻 {inst["congestion_from"]} 起出发的整段道路时间×{inst["congestion_mult"]}（按下楼回到地面后离开的时刻判断）。连续配送上限 {inst["max_carry"]} 单，满则先回 W。
取消订单（不必配送）：{_compact(inst["cancel_ids"])}。从时刻 {inst["flood"][0]} 起楼宇 {inst["flood"][1]} 因洪涝不可进入（须在此前完成该楼全部订单）。
规则：
- 到达楼宇地面后先完成需要的登记（登记在楼外进行，不受封闭影响），之后若处于封闭则等到结束；然后若该时刻处于该楼宇停运区间内，本次上楼步行，每层 2 分钟；否则乘电梯，每层 1 分钟。上楼期间状态变化不影响本次上楼。送达时刻 = 到达所在楼层的时刻。
- 送达后回到地面固定每层 1 分钟（不受电梯状态影响），再出发去下一单；下一单在同一楼宇时道路分钟为 0，仍需下楼再上楼。最后一单送达即结束，不再下楼。
- 回 W 后连续配送计数重新从 0 开始。除上面规定的登记、封闭等待外，不得在任何地点主动停留。
- 送达时刻 > deadline 为迟到；deadline 不限制可行性。
- 目标：先使迟到订单数最少，在此前提下使最后一单送达时刻最小。
- 互斥突发：洪涝封楼与楼宇封闭候选中只生效一条——开始时刻最早者；同时刻取洪涝优先。未生效者视为不存在。
- 反事实：若改为另一条突发生效，最短完成相关目标下的最后送达时刻为对照值。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `total`：整数，最后一单送达时刻。"""


def gen_nx18(_rng):
    return copy.deepcopy(PACK["NX-18"])


def solve_nx18(inst):
    from eval_bank_20260925 import reasoning_gen as g
    live = g._apply_mutex_delivery(inst)
    best = g._ranked(live, g._key18(live))[0]
    cf = g._ranked(g._apply_mutex_delivery(g._other_shock(inst, live, g.PRIO_DELIVERY)), g._key18(inst))[0]
    return {
        "route": best[1], "arrivals": best[2], "late": best[3], "elevator_walk": best[5],
        "cf_total": best[4] if inst.get("cf_equals_factual") else cf[4],
    }


def extra_nx18(inst, ans):
    from eval_bank_20260925 import reasoning_gen as g
    live = g._apply_mutex_delivery(inst)
    rows = g._ranked(live, g._key18(live))
    return rows[0][0] < rows[1][0] and len(ans["route"]) >= 4


def prompt_nx18(inst):
    from eval_bank_20260925.reasoning_gen import _compact, _city_rows
    orders = [[oid, o["building"], o["floor"], o["ready"], o["deadline"]] for oid, o in sorted(inst["orders"].items())]
    return f"""
冷藏骑手 0 分钟在站点 W（地面），完成全部订单，顺序自选。任意两地点之间道路双向可走，行驶分钟表每行 `[地点, 地点, 分钟]`：{_compact(_city_rows(inst))}。
订单表每行 `[id, 楼宇, 楼层, ready, deadline]`：{_compact(orders)}。
电梯停运区间（半开区间 [开始, 结束)）：{_compact(inst["outages"])}。
首次进入楼宇需在地面登记（分钟，同一楼宇再次进入不再登记）：{_compact(inst["register"])}。
楼宇封闭区间（半开）：{_compact(inst["closed"])}。从时刻 {inst["congestion_from"]} 起出发的整段道路时间×{inst["congestion_mult"]}（按下楼回到地面后离开的时刻判断）。连续配送上限 {inst["max_carry"]} 单，满则先回 W。冷链时限 ready+{inst["cold_limit"]}，超时亦计迟到。
取消订单（不必配送）：{_compact(inst["cancel_ids"])}。从时刻 {inst["flood"][0]} 起楼宇 {inst["flood"][1]} 因洪涝不可进入（须在此前完成该楼全部订单）。
规则：
- 到达楼宇地面后先完成需要的登记（登记在楼外进行，不受封闭影响），之后若处于封闭则等到结束；然后若当前时刻早于该订单 ready，在地面等到 ready；开始上楼的时刻若处于该楼宇停运区间内，本次上楼步行，每层 2 分钟，否则乘电梯，每层 1 分钟。上楼期间状态变化不影响本次上楼。送达时刻 = 到达所在楼层的时刻。
- 送达后回到地面固定每层 1 分钟（不受电梯状态影响），再出发去下一单；下一单在同一楼宇时道路分钟为 0，仍需下楼再上楼。最后一单送达即结束。
- 只有已连续送满 {inst["max_carry"]} 单且仍有未送订单时才回 W（回 W 后重新计数）；未满不得提前回 W。除上面规定的登记、封闭等待和等到 ready 外，不得在任何地点主动停留。
- 送达时刻 > deadline，或 > ready + {inst["cold_limit"]}，均为迟到。
- 目标：先使迟到订单数最少，在此前提下使最后一单送达时刻最小。
- 互斥突发：洪涝封楼与楼宇封闭候选中只生效一条——开始时刻最早者；同时刻洪涝优先。未生效者视为不存在。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `elevator_walk`：整数，全程步行上楼所用分钟数之和（乘电梯与下楼不计）。"""


# ---------------------------------------------------------------------------
# NX-17
# ---------------------------------------------------------------------------

def gen_nx17(_rng):
    return copy.deepcopy(PACK["NX-17"])


def solve_nx17(inst):
    from eval_bank_20260925 import reasoning_gen as g
    live = g._apply_mutex_nx17(inst)
    ans = g._solve_nx17_core(live)
    cf = g._solve_nx17_core(g._apply_mutex_nx17(g._other_shock(inst, live, g.PRIO_NX17)))
    ans = dict(ans)
    ans["cf_arrive"] = ans["arrive"] if inst.get("cf_equals_factual") else cf["arrive"]
    return ans


def extra_nx17(inst, ans):
    from eval_bank_20260925 import reasoning_gen as g
    live = g._apply_mutex_nx17(inst)
    found = g._paths_nx17(live)
    if not found or not ans["path"]:
        return False
    if len(found) >= 2 and not (found[0][0], found[0][1], found[0][2]) < (found[1][0], found[1][1], found[1][2]):
        return False
    free = g._solve_nx17_core(dict(inst, closures=[], budget=999, transfer={}, avoid=[], max_hops=99, slow_after=10**9, slow_mult=1, hub_fail=None))
    return free["path"] != ans["path"]


def prompt_nx17(inst):
    from eval_bank_20260925.reasoning_gen import _compact
    hops = inst.get("max_hops", 10**9)
    hop_line = f"- 路径边数（站点数−1）不得超过 {hops}。\n" if hops < 10**8 else ""
    return f"""
有向线路网，站点 {"、".join(inst["nodes"])}。线路表每行 `[起点, 终点, 分钟, 费用]`，只能按起点→终点方向乘坐：{_compact(inst["edges"])}。
封闭表每行 `[起点, 终点, 开始, 结束]`：该线路在半开区间 [开始, 结束) 内封闭：{_compact(inst["closures"])}。
从 {inst["src"]} 于 0 分钟出发前往 {inst["dst"]}，预算 {inst["budget"]}。
约束：
- 在下列中转站换乘需固定耗时（分钟），其余站点为 0：{_compact(inst["transfer"])}。
- 可以在站内等待后再出发（等待时长计入时间），但窗口内不得在该站停留或换乘（即使换乘不等待也不行）。
- 禁止驻留/换乘窗口 `[站点,开始,结束]`（半开）：{_compact(inst["avoid"])}。
- 进入时刻 ≥ {inst["slow_after"]} 的线路分钟 ×{inst["slow_mult"]}。
- 换乘枢纽故障：从时刻 {inst["hub_fail"][1]} 起站点 {inst["hub_fail"][0]} 不可进入/换乘（终点除外）。
{hop_line}- 只能进入在进入时刻未封闭的线路；已进入的线路不受之后封闭影响。
- 路径不得重复经过同一站点；累计费用不超过预算。
- 可行路径的比较次序：到达时刻小者优先，其次费用小者优先，再按站点序列字典序。
- 互斥突发：分时封闭与枢纽故障至多生效一条——比较封闭开始时刻与枢纽故障时刻，较早者生效；同时刻优先封闭。未生效者视为不存在。
输出 JSON 对象，只含以下字段：
- `path`：数组，最优可行路径的站点序列（含起终点）。
- `arrive`：整数，最优路径到达 {inst["dst"]} 的时刻。
- `cost`：整数，最优路径费用。
- `alternatives`：数组，按上述比较次序紧随最优路径之后的至多 3 条可行路径，每项 `[站点序列, 到达时刻, 费用]`；不足 3 条有多少列多少。
- `reason`：字符串；存在可行路径时为空字符串 `""`；不存在时为 `no_budget_path`。"""
