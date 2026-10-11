"""20261014 推理题（NX-09..NX-18）实例生成器、参考求解器与关键条件。

遵循 docs/question-bank-methodology-20261008.md：
- 分档 2A/3B/3C/2D（TIERS）；难度来自依赖与状态转移，规模只取“够用”。
- 每题列出关键条件（CONDITIONS）；删除任一关键条件，参考答案至少一个关键字段必须变化（生成时检查，CI 用独立模拟器复查）。
- C 档要求答案轨迹落在半开区间/就绪等边界时刻上；D 档要求约束改变无约束最优解。
- 种子从 BASE_SEED + 题号×100000 起逐个尝试，取第一个满足接受条件的实例；答案键全部由求解器计算。
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import random
from typing import Any, Callable

VERSION = "20261014"
BASE_SEED = 20261014
MAX_TRIES = 20000

TIERS = {
    "NX-09": "A", "NX-10": "A",
    "NX-11": "B", "NX-14": "B", "NX-15": "B",
    "NX-12": "C", "NX-13": "C", "NX-18": "C",
    "NX-16": "D", "NX-17": "D",
}

# 质量门禁记录（docs/question-bank-quality-gate-20261006.md）。主能力一律为“推理”。
GATE = {
    "NX-09": {"anchor": "门诊分诊台按到达与急诊级别把患者派到诊室，感染患者后诊室需清场，门诊有关门时刻。",
              "cost": "错误排程：急诊被普通患者挡住、关门前应接诊者被漏掉。",
              "capability": "推理", "transfer": "换成客服坐席/维修工位派单，规则不变时同一推导成立。"},
    "NX-10": {"anchor": "充电运营按到达顺序为预约车辆确定桩位和时段，电价分时、桩有维护预约。",
              "cost": "错误付款与错误拒单：车主多付电费或被错误拒绝。",
              "capability": "推理", "transfer": "换成会议室/机位按顺序订最低价时段。"},
    "NX-11": {"anchor": "冷链仓按订单锁定批次、按窗口装车，订单可取消、批次会过期。",
              "cost": "错误库存：锁错批次导致过期发货或可售量错误。",
              "capability": "推理", "transfer": "换成医院血袋/疫苗批次的锁定与出库。"},
    "NX-12": {"anchor": "外卖骑手在多栋楼宇间安排配送顺序，电梯按时段停运。",
              "cost": "错误排程：骑手按错顺序导致整体送达更晚、迟到判定错误。",
              "capability": "推理", "transfer": "换成快递员多楼宇派件或巡检员巡楼顺序。"},
    "NX-13": {"anchor": "航司运控在延误、关闭事件后为航段重新确定执行机组。",
              "cost": "错误排程与合规：机组位置不符、转场不足或超执勤上限仍被派飞。",
              "capability": "推理", "transfer": "换成长途司机/列车乘务按班次和工时上限换班。"},
    "NX-14": {"anchor": "充电站按优先级排队，等待过久的车辆逐步提升优先级（防饥饿）。",
              "cost": "错误排程与付款：车辆开始/结束时刻错，费用与峰时费用统计错误。",
              "capability": "推理", "transfer": "换成打印/算力队列的老化优先级调度。"},
    "NX-15": {"anchor": "病房收治：感染患者只能入隔离床，离床后需清洁，到点停止收治。",
              "cost": "感染控制与排程：感染患者被安排到普通床或清洁未完成即入住。",
              "capability": "推理", "transfer": "换成实验室洁净间与普通间的样本排程。"},
    "NX-16": {"anchor": "水果店按箱进货，货物两天内售完，热天不能进货且当天清库。",
              "cost": "错误采购：利润下降、报废增加。",
              "capability": "推理", "transfer": "换成面包房/鲜花店的整箱采购计划。"},
    "NX-17": {"anchor": "通勤者在有向线路网中按预算换乘，部分线路分时封闭。",
              "cost": "错误路线：选到封闭线路或超预算路线。",
              "capability": "推理", "transfer": "换成物流干线在限行时段与运费预算下的路由。"},
    "NX-18": {"anchor": "冷藏骑手配送：订单有出餐时刻和截止时刻，楼宇电梯分时停运。",
              "cost": "错误排程：迟到单数增加、冷藏品超时。",
              "capability": "推理", "transfer": "换成药品配送按备药时刻与截止时刻排线。"},
}


def _ids(prefix: str, n: int) -> list[str]:
    width = len(str(n))
    return [f"{prefix}{i:0{width}d}" for i in range(1, n + 1)]


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _rate(tariff, minute):
    for start, end, price in tariff:
        if start <= minute < end:
            return price
    return tariff[-1][2]


# ---------------------------------------------------------------------------
# 通用派位（NX-09 / NX-15）：非空闲，单元按编号依次取最高优先级的可服务者
# ---------------------------------------------------------------------------

def _dispatch(units, patients, clean, close, eligible, emergency_first=True, caps=None, light_clean=0, infect_deadline=None):
    free_at = {u: 0 for u in units}
    used = {u: 0 for u in units}
    pending = set(patients)
    served, last_clean = [], {}
    t = 0
    while True:
        changed = False
        if t < close:
            for unit in units:
                if free_at[unit] > t:
                    continue
                if caps and used[unit] >= caps.get(unit, 10**9):
                    continue
                ready = [pid for pid in pending if patients[pid]["arrive"] <= t and eligible(unit, patients[pid])]
                if infect_deadline is not None:
                    ready = [pid for pid in ready if (not patients[pid]["infectious"]) or t < infect_deadline]
                if not ready:
                    continue
                ready.sort(key=lambda pid: ((patients[pid]["kind"] != "emergency") if emergency_first else 0, patients[pid]["arrive"], pid))
                pid = ready[0]
                p = patients[pid]
                end = t + p["service"]
                served.append([pid, unit, t, end])
                pending.discard(pid)
                used[unit] += 1
                extra = clean if p["infectious"] else light_clean
                free_at[unit] = end + extra
                if p["infectious"]:
                    last_clean[unit] = end + clean
                changed = True
        if changed:
            continue
        future = [patients[pid]["arrive"] for pid in pending if patients[pid]["arrive"] > t]
        future += [v for v in free_at.values() if v > t]
        future = [v for v in future if v < close]
        if not pending or not future:
            break
        t = min(future)
    served.sort(key=lambda row: (row[2], row[1]))
    return served, pending, last_clean


def _patients(rng, n, arrive_max, p_emerg, p_inf, svc_e, svc_n):
    out = {}
    for pid in _ids("P", n):
        kind = "emergency" if rng.random() < p_emerg else "normal"
        out[pid] = {"arrive": rng.randint(0, arrive_max), "kind": kind, "infectious": rng.random() < p_inf,
                    "service": rng.randint(*svc_e) if kind == "emergency" else rng.randint(*svc_n)}
    return out


def _patient_rows(patients):
    return [[pid, v["arrive"], v["kind"][0].upper(), int(v["infectious"]), v["service"]] for pid, v in sorted(patients.items())]


# NX-09 (A) -----------------------------------------------------------------

def _gen_nx09(rng):
    return {"rooms": ["R1", "R2", "R3"], "clean": 5, "close": 50, "emergency_first": True, "no_infectious": ["R3"],
            "room_cap": {"R1": 2, "R2": 3, "R3": 3}, "infect_cutoff": 35,
            "patients": _patients(rng, 12, 40, 0.3, 0.3, (8, 14), (5, 10))}


def _solve_nx09(inst):
    p = inst["patients"]
    banned = set(inst["no_infectious"])
    served, pending, _ = _dispatch(inst["rooms"], p, inst["clean"], inst["close"],
                                   lambda u, x: not (x["infectious"] and u in banned), inst["emergency_first"],
                                   caps=inst["room_cap"], infect_deadline=inst["infect_cutoff"])
    return {"served": served,
            "waiting": sorted(pending, key=lambda pid: (p[pid]["arrive"], pid)),
            "last_end": max(row[3] for row in served),
            "infectious_rooms": sorted({row[1] for row in served if p[row[0]]["infectious"]})}


def _prompt_nx09(inst):
    return f"""
门诊有诊室 {", ".join(inst["rooms"])}，0 分钟时全部空闲。患者表每行为 `[id, 到达分钟, 类型(E=急诊/N=普通), 是否感染(1/0), 服务分钟]`：
{_compact(_patient_rows(inst["patients"]))}
约束：
- 一个诊室同一时刻最多接诊一人，接诊开始后连续服务到结束；感染患者结束后该诊室需清场 {inst["clean"]} 分钟，清场期间不可接诊。
- {"、".join(inst["no_infectious"]) or "无"} 不接诊感染患者。
- 各诊室当天最多接诊人数：{_compact(inst["room_cap"])}。
- 感染患者开始接诊分钟必须严格小于 {inst["infect_cutoff"]}。
- 只有已到达（到达分钟 ≤ 开始分钟）的患者可以开始接诊；开始分钟必须严格小于关门时刻 {inst["close"]}。
- 诊室不得闲置：任一时刻若某诊室可用且有已到达未开始、该诊室可接诊的患者（且未关门），该时刻必须开始接诊。
- 优先级：急诊高于普通；同类型到达早者优先；再按 id。同一时刻有多个诊室可用时按编号从小到大依次安排，每个诊室取当时它可接诊的最高优先级患者。
输出 JSON 对象，只含以下字段：
- `served`：数组，每项 `[id, 诊室, 开始分钟, 结束分钟]`，按开始分钟、诊室编号升序。
- `waiting`：数组，到关门仍未开始接诊的患者 id（字符串），按到达分钟、id 升序；没有则为 `[]`。
- `last_end`：整数，所有接诊的最大结束分钟（不含清场）。
- `infectious_rooms`：数组，接诊过感染患者的诊室，按编号升序。"""


# NX-10 (A) -----------------------------------------------------------------

def _gen_nx10(rng):
    piles = {"P1": 2, "P2": 3, "P3": 4}
    horizon = 40
    cuts = sorted(rng.sample(range(4, horizon), 3))
    bounds = [0, *cuts, horizon]
    tariff = [[bounds[i], bounds[i + 1], rng.randint(1, 4)] for i in range(len(bounds) - 1)]
    reservations = {}
    for pile in piles:
        a = rng.randint(0, horizon - 8)
        reservations[pile] = [[a, a + rng.randint(3, 8)]]
    vehicles = []
    for vid in _ids("V", 10):
        arrive = rng.randint(0, 28)
        vehicles.append([vid, arrive, rng.randint(4, 16), min(horizon, arrive + rng.randint(3, 12))])
    return {"piles": piles, "min_energy": {"P3": 10}, "gap": 2, "max_concurrent": 2, "tariff": tariff, "reservations": reservations, "vehicles": vehicles}


def _plan_nx10(inst):
    occupied = {pile: [tuple(w) for w in ws] for pile, ws in inst["reservations"].items()}
    horizon = inst["tariff"][-1][1]
    load = [0] * (horizon + 64)
    gap = inst.get("gap", 0)
    max_c = inst.get("max_concurrent", 10**9)
    assign, rejected, ties = [], [], 0
    for vid, arrive, energy, deadline in inst["vehicles"]:
        cands = []
        for pile, power in sorted(inst["piles"].items()):
            if energy < inst["min_energy"].get(pile, 0):
                continue
            dur = math.ceil(energy / power)
            for start in range(arrive, deadline - dur + 1):
                end = start + dur
                if any(start < b + gap and end + gap > a for a, b in occupied[pile]):
                    continue
                if any(load[m] >= max_c for m in range(start, end)):
                    continue
                cands.append((sum(_rate(inst["tariff"], m) for m in range(start, end)), end, pile, start))
        if not cands:
            rejected.append(vid)
            continue
        cands.sort()
        ties += len(cands) > 1 and cands[0][:2] == cands[1][:2]
        cost, end, pile, start = cands[0]
        occupied[pile].append((start, end))
        for m in range(start, end):
            load[m] += 1
        assign.append([vid, pile, start, end, cost])
    return {"assign": assign, "rejected": rejected, "total_cost": sum(r[4] for r in assign)}, ties


def _solve_nx10(inst):
    return _plan_nx10(inst)[0]


def _extra_nx10(inst, ans):
    return _plan_nx10(inst)[1] == 0 and len(ans["rejected"]) >= 1


def _prompt_nx10(inst):
    piles = ", ".join(f"{k} 功率 {v}" for k, v in inst["piles"].items())
    res = "；".join(f"{k}:" + "、".join(f"[{a},{b})" for a, b in v) for k, v in inst["reservations"].items())
    return f"""
充电桩：{piles}。预约占用（半开区间，不可充电）：{res}。
电价表每项 `[开始, 结束, 每分钟价格]`（半开区间）：{_compact(inst["tariff"])}。
车辆表每行 `[id, 到达, 电量, deadline]`：{_compact(inst["vehicles"])}。
约束：
- 车辆在某桩充电时长为 `ceil(电量/功率)` 分钟，必须连续；开始时刻为不早于到达的整数，结束时刻 ≤ deadline。
- 同一桩任意时刻最多一辆车，不得与预约或已确定的车辆重叠（半开区间）。
- 费用 = 充电各分钟所在时段价格之和，与功率无关。
- 同一桩相邻两段充电（含预约）之间至少空闲 {inst["gap"]} 分钟。
- 任意时刻全站同时充电车辆数不超过 {inst["max_concurrent"]}（预约不计入）。
- 桩的最低电量要求（电量低于该值的车辆不能使用该桩）：{_compact(inst["min_energy"])}；未列出的桩无要求。
- 车辆按表中顺序确定方案；每辆车的方案必须是：在与之前已确定方案不冲突的全部可行（桩, 开始时刻）中，费用最低；费用相同则结束时刻最早；再按桩编号。没有可行方案的车辆记为拒绝，不占用任何时段。
输出 JSON 对象，只含以下字段：
- `assign`：数组，每项 `[车辆id, 桩, 开始, 结束, 费用]`，按车辆表顺序，只含被接受的车辆。
- `rejected`：数组，被拒绝车辆 id，按车辆表顺序；没有则为 `[]`。
- `total_cost`：整数，assign 中费用之和。"""


# NX-11 (B) 批次锁定、取消归还、过期与装车 -------------------------------------

def _gen_nx11(rng):
    zones = {"A": "cold", "B": "cold", "C": "frozen", "D": "frozen"}
    batches = {b: {"qty": rng.randint(4, 9), "expiry": rng.randint(12, 45), "zone": zones[b]} for b in "ABCD"}
    oids = _ids("O", 10)
    times = sorted(rng.randint(0, 40) for _ in oids)
    events = [{"t": t, "op": "ORDER", "id": o, "qty": rng.randint(2, 6),
               "zone": rng.choice(["cold", "frozen"]), "vip": int(rng.random() < 0.3)} for o, t in zip(oids, times)]
    for oid in rng.sample(oids[:6], 2):
        t0 = next(e["t"] for e in events if e.get("id") == oid)
        events.append({"t": min(44, t0 + rng.randint(1, 8)), "op": "CANCEL", "id": oid})
    for t in sorted(rng.sample(range(6, 48), 3)):
        events.append({"t": t, "op": "LOAD"})
    a = rng.randint(5, 15)
    windows = [[a, a + rng.randint(6, 12)]]
    b = windows[0][1] + rng.randint(4, 10)
    windows.append([b, b + rng.randint(6, 12)])
    rank = {"ORDER": 0, "CANCEL": 1, "LOAD": 2}
    events.sort(key=lambda e: (e["t"], rank[e["op"]], e.get("id", "")))
    return {"batches": batches, "events": events, "windows": windows, "capacity": 9, "max_open": 2, "vip_first": True}


def _solve_nx11(inst):
    free = {b: v["qty"] for b, v in inst["batches"].items()}
    expiry = {b: v["expiry"] for b, v in inst["batches"].items()}
    zone = {b: v["zone"] for b, v in inst["batches"].items()}
    locks, loaded, rejected, state = [], [], [], {}
    for e in inst["events"]:
        t = e["t"]
        if e["op"] == "ORDER":
            open_n = {b: sum(1 for s in state.values() if s["batch"] == b and s["status"] == "locked") for b in free}
            ok = [b for b in sorted(free) if expiry[b] > t and free[b] >= e["qty"] and open_n[b] < inst["max_open"] and zone[b] == e["zone"]]
            if not ok:
                rejected.append(e["id"])
                continue
            b = min(ok, key=lambda x: (expiry[x], x))
            free[b] -= e["qty"]
            locks.append([e["id"], b, e["qty"]])
            state[e["id"]] = {"batch": b, "qty": e["qty"], "t": t, "status": "locked", "vip": e.get("vip", 0)}
        elif e["op"] == "CANCEL":
            s = state.get(e["id"])
            if s and s["status"] == "locked":
                s["status"] = "cancelled"
                free[s["batch"]] += s["qty"]
        elif any(a <= t < z for a, z in inst["windows"]):
            room = inst["capacity"]
            key = (lambda kv: (0 if kv[1].get("vip") else 1, kv[1]["t"], kv[0])) if inst.get("vip_first", True) else (lambda kv: (kv[1]["t"], kv[0]))
            for oid, s in sorted(state.items(), key=key):
                if s["status"] == "locked" and expiry[s["batch"]] > t and s["qty"] <= room:
                    room -= s["qty"]
                    s["status"] = "loaded"
                    loaded.append(oid)
    return {"locks": locks, "loaded": loaded, "free": free, "rejected": rejected}


def _extra_nx11(inst, ans):
    # 状态交互：去掉取消后，至少一张“取消之后”的订单锁定批次改变或从拒绝变为锁定
    mut = _drop_cancel(inst)
    other = _solve_nx11(mut)
    cancel_ids = {e["id"] for e in inst["events"] if e["op"] == "CANCEL"}
    a = {l[0]: l[1] for l in ans["locks"] if l[0] not in cancel_ids}
    b = {l[0]: l[1] for l in other["locks"] if l[0] not in cancel_ids}
    return a != b and len(ans["loaded"]) >= 3 and len(ans["rejected"]) >= 1


def _drop_cancel(inst):
    x = copy.deepcopy(inst)
    x["events"] = [e for e in x["events"] if e["op"] != "CANCEL"]
    return x


def _prompt_nx11(inst):
    batches = [[b, v["qty"], v["expiry"], v["zone"]] for b, v in inst["batches"].items()]
    ev = []
    for e in inst["events"]:
        if e["op"] == "ORDER":
            ev.append([e["t"], "ORDER", e["id"], e["qty"], e["zone"], e["vip"]])
        elif e["op"] == "CANCEL":
            ev.append([e["t"], "CANCEL", e["id"]])
        else:
            ev.append([e["t"], "LOAD"])
    return f"""
批次表每行 `[批次, 数量, expiry, 温区]`：{_compact(batches)}。批次在 expiry 时刻及以后视为过期。
装车窗口（半开区间）：{_compact(inst["windows"])}；每次装车容量 {inst["capacity"]}。
事件按表中顺序发生，每行 `[时刻, 类型, ...]`：{_compact(ev)}。
约束：
- ORDER `[t,"ORDER",订单,数量,温区,vip]`：订单必须整单锁定在温区相同的单个批次上，该批次在 t 未过期、未锁定数量 ≥ 订单数量，且该批次上处于“锁定且未装车”的订单少于 {inst["max_open"]} 个；满足条件的批次中必须选 expiry 最小者，同 expiry 选批次名小者。没有则拒绝。vip=1 为加急。
- CANCEL `[t,"CANCEL",订单]`：仅对处于锁定且未装车的订单生效，锁定数量归还该批次；其余情况无效果。
- LOAD `[t,"LOAD"]`：t 不在任何装车窗口内则无效果。否则先装 vip=1，再装其余；同组内按锁定时刻、订单 id 次序：所锁批次在 t 已过期的不装；累计不超过容量的装车，装不下的跳过。未装车的保持锁定。
输出 JSON 对象，只含以下字段：
- `locks`：数组，每项 `[订单, 批次, 数量]`，所有锁定成功过的订单（含之后被取消的），按锁定事件顺序。
- `loaded`：数组，已装车订单 id，按装车先后。
- `free`：对象，键为每个批次名，值为全部事件结束后该批次未被锁定的数量（已装车数量不再计入未锁定）。
- `rejected`：数组，被拒绝订单 id，按事件顺序。"""


# NX-14 (B) 老化优先级排队 ----------------------------------------------------

def _gen_nx14(rng):
    piles = {"S1": 2, "S2": 1}
    cuts = sorted(rng.sample(range(5, 40), 2))
    bounds = [0, *cuts, 200]
    tariff = [[bounds[i], bounds[i + 1], p] for i, p in enumerate(rng.sample([1, 2, 3], 3))]
    peak = max(tariff, key=lambda r: r[2])[:2]
    cars = [[cid, rng.randint(0, 30), rng.randint(3, 10), rng.randint(1, 3)] for cid in _ids("V", 10)]
    return {"piles": piles, "min_prio": {"S2": 2}, "tariff": tariff, "peak": peak, "aging": 5,
            "aging_cap": 1, "max_wait": 18, "peak_ban": {"S1": True}, "cars": cars}


def _solve_nx14(inst):
    cars = {c: {"arrive": a, "energy": e, "prio": p} for c, a, e, p in inst["cars"]}
    free_at = {p: 0 for p in inst["piles"]}
    pending, sched, t = set(cars), [], 0
    aging = inst["aging"]
    aging_cap = inst.get("aging_cap", 10**9)
    max_wait = inst.get("max_wait", 10**9)
    peak_a, peak_b = inst["peak"]
    peak_ban = inst.get("peak_ban", {})

    def eff(c):
        bonus = min((t - cars[c]["arrive"]) // aging, aging_cap) if aging else 0
        return cars[c]["prio"] + bonus

    while pending:
        for c in [c for c in list(pending) if cars[c]["arrive"] <= t and t - cars[c]["arrive"] > max_wait]:
            pending.discard(c)
        progressed = False
        for pile in sorted(inst["piles"]):
            if free_at[pile] > t:
                continue
            if peak_ban.get(pile) and peak_a <= t < peak_b:
                continue
            ready = [c for c in pending if cars[c]["arrive"] <= t and cars[c]["prio"] >= inst["min_prio"].get(pile, 0)]
            if not ready:
                continue
            c = min(ready, key=lambda c: (-eff(c), cars[c]["arrive"], c))
            end = t + math.ceil(cars[c]["energy"] / inst["piles"][pile])
            sched.append([c, pile, t, end, sum(_rate(inst["tariff"], m) for m in range(t, end))])
            free_at[pile] = end
            pending.discard(c)
            progressed = True
        if progressed:
            continue
        future = [cars[c]["arrive"] for c in pending if cars[c]["arrive"] > t] + [v for v in free_at.values() if v > t]
        future += [cars[c]["arrive"] + max_wait + 1 for c in pending if cars[c]["arrive"] <= t]
        future = [v for v in future if v > t]
        if not pending or not future:
            break
        t = min(future)
    sched.sort(key=lambda r: (r[2], r[1]))
    a, b = inst["peak"]
    peak_cost = sum(_rate(inst["tariff"], m) for _c, _p, s, e, _x in sched for m in range(s, e) if a <= m < b)
    return {"schedule": sched, "peak_cost": peak_cost, "finish_order": [r[0] for r in sorted(sched, key=lambda r: (r[3], r[0]))]}


def _extra_nx14(inst, ans):
    arrive = {c: a for c, a, _e, _p in inst["cars"]}
    left = len(inst["cars"]) - len(ans["schedule"])
    return (sum(1 for r in ans["schedule"] if r[2] > arrive[r[0]]) >= 2 and ans["peak_cost"] > 0
            and left >= 1 and len(ans["schedule"]) >= 5)


def _prompt_nx14(inst):
    piles = ", ".join(f"{k} 功率 {v}" for k, v in inst["piles"].items())
    a, b = inst["peak"]
    return f"""
充电桩：{piles}，0 分钟全部空闲。电价表每项 `[开始, 结束, 每分钟价格]`（半开区间）：{_compact(inst["tariff"])}。
车辆表每行 `[id, 到达, 电量, 初始priority]`：{_compact(inst["cars"])}。
约束：
- 车辆在桩上充电时长为 `ceil(电量/功率)` 分钟，开始后不可中断、不可换桩；同一桩同一时刻最多一辆车。
- 桩的准入（初始priority 低于该值的车辆不能使用该桩）：{_compact(inst["min_prio"])}；未列出的桩无要求。
- 峰时 [{inst["peak"][0]},{inst["peak"][1]}) 禁用的桩：{_compact([k for k,v in inst["peak_ban"].items() if v])}。
- 等待超过 {inst["max_wait"]} 分钟仍未开始则离开。
- 桩不得闲置：任一时刻若某桩空闲、未被禁用，且有已到达未开始、可使用该桩的车辆，该时刻必须开始充电。
- 车辆在时刻 t 的有效 priority = 初始priority + min(floor((t − 到达) / {inst["aging"]}), {inst["aging_cap"]})。桩接车时选有效 priority 最大者；相同则到达早者优先，再按 id。多空闲桩时编号小的先接。
- 费用 = 充电各分钟所在时段价格之和，与功率无关。
输出 JSON 对象，只含以下字段：
- `schedule`：数组，每项 `[id, 桩, 开始, 结束, 费用]`，按开始、桩编号升序。
- `peak_cost`：整数，所有车辆落在 [{a},{b}) 内各分钟的费用之和。
- `finish_order`：数组，车辆 id 按结束时刻升序，同刻按 id。"""


# NX-15 (B) 隔离床 -------------------------------------------------------------

def _gen_nx15(rng):
    return {"beds": ["B1", "B2", "B3", "B4"], "isolation": ["B1"], "emergency_only": ["B4"], "clean": 6, "light_clean": 4,
            "bed_cap": {"B1": 2, "B2": 2, "B3": 2, "B4": 2}, "close": 55, "emergency_first": True,
            "patients": _patients(rng, 12, 45, 0.35, 0.35, (8, 14), (5, 11))}


def _solve_nx15(inst):
    iso, eo = set(inst["isolation"]), set(inst["emergency_only"])
    p = inst["patients"]
    served, pending, last_clean = _dispatch(inst["beds"], p, inst["clean"], inst["close"],
                                           lambda bed, x: ((not x["infectious"]) or bed in iso) and (bed not in eo or x["kind"] == "emergency"), inst["emergency_first"], caps=inst["bed_cap"], light_clean=inst["light_clean"])
    return {"beds": served, "waiting": sorted(pending, key=lambda pid: (p[pid]["arrive"], pid)),
            "disinfect_until": dict(sorted(last_clean.items())),
            "emergency_wait": sum(r[2] - p[r[0]]["arrive"] for r in served if p[r[0]]["kind"] == "emergency")}


def _prompt_nx15(inst):
    return f"""
病床 {", ".join(inst["beds"])}，其中隔离床为 {", ".join(inst["isolation"])}，0 分钟全部空闲。患者表每行 `[id, 到达分钟, 类型(E=急诊/N=普通), 是否感染(1/0), 占床分钟]`：
{_compact(_patient_rows(inst["patients"]))}
约束：
- 一张床同一时刻最多一名患者，占床连续到结束；感染患者只能使用隔离床，非感染患者可用任何床；感染患者离床后该床清洁 {inst["clean"]} 分钟，清洁结束前不可用。
- {"、".join(inst["emergency_only"])} 只收急诊患者。
- 各床当天最多收治人数：{_compact(inst["bed_cap"])}。
- 非感染患者离床后该床轻清 {inst["light_clean"]} 分钟。
- 只有已到达的患者可以上床；上床时刻必须严格小于停止收治时刻 {inst["close"]}。
- 床位不得闲置：任一时刻若某床可用且存在已到达、未上床且可用该床的患者（且未停止收治），该时刻必须安排。
- 优先级：急诊高于普通；同类型到达早者优先；再按 id。同一时刻有多张床可用时按床号从小到大依次安排，每张床取当时可用该床的最高优先级患者。
输出 JSON 对象，只含以下字段：
- `beds`：数组，每项 `[id, 床, 上床分钟, 离床分钟]`，按上床分钟、床号升序。
- `waiting`：数组，到停止收治仍未上床的患者 id，按到达分钟、id 升序；没有则为 `[]`。
- `disinfect_until`：对象，只含接收过感染患者的床，值为该床最后一次清洁结束的分钟。
- `emergency_wait`：整数，已上床的急诊患者（上床分钟 − 到达分钟）之和。"""


# NX-12 / NX-18 (C) 配送 -----------------------------------------------------

def _gen_city(rng, n_buildings, max_floor):
    names = ["W"] + [f"L{i}" for i in range(1, n_buildings + 1)]
    pts = {n: (rng.randint(0, 6), rng.randint(0, 6)) for n in names}
    roads = {}
    for a, b in itertools.combinations(names, 2):
        roads[f"{a}-{b}"] = max(2, abs(pts[a][0] - pts[b][0]) + abs(pts[a][1] - pts[b][1]) + rng.randint(0, 2))
    outages = {}
    for n in names[1:]:
        a = rng.randint(0, 30)
        outages[n] = [[a, a + rng.randint(6, 18)]]
    return roads, outages


def _road(roads, a, b):
    return 0 if a == b else roads.get(f"{a}-{b}", roads.get(f"{b}-{a}"))


def _deliver(inst, route):
    pos, clock, walk, prev_floor = "W", 0, 0, 0
    visited, arrivals, boundary, carry = set(), [], 0, 0
    orders = inst["orders"]
    down_rate = inst.get("down_rate", 1)
    cong_from = inst.get("congestion_from", 10**9)
    cong_mult = inst.get("congestion_mult", 1)
    closed = inst.get("closed", {})
    max_carry = inst.get("max_carry", 10**9)
    cold_limit = inst.get("cold_limit")

    def travel(a, b, t0):
        d = _road(inst["roads"], a, b)
        return d * cong_mult if t0 >= cong_from else d

    for oid in route:
        if carry >= max_carry and pos != "W":
            clock += prev_floor * down_rate + travel(pos, "W", clock)
            pos, prev_floor, carry = "W", 0, 0
        o = orders[oid]
        b = o["building"]
        clock += prev_floor * down_rate + travel(pos, b, clock)
        if b not in visited:
            clock += inst.get("register", {}).get(b, 0)
            visited.add(b)
        for a, z in closed.get(b, []):
            if a <= clock < z:
                if clock == a: boundary += 1
                clock = z
        ready = o.get("ready", 0)
        if clock == ready and ready > 0: boundary += 1
        clock = max(clock, ready)
        spans = inst["outages"][b]
        if any(clock in (a, z) for a, z in spans): boundary += 1
        stopped = any(a <= clock < z for a, z in spans)
        up = o["floor"] * (2 if stopped else 1)
        walk += up if stopped else 0
        clock += up
        arrivals.append([oid, clock])
        pos, prev_floor, carry = b, o["floor"], carry + 1
    late = []
    for oid, t in arrivals:
        o = orders[oid]
        cold_ok = True if cold_limit is None else t <= o.get("ready", 0) + cold_limit
        if t > o["deadline"] or not cold_ok: late.append(oid)
    return arrivals, sorted(late), clock, walk, boundary


def _ranked(inst, key):
    rows = []
    for route in itertools.permutations(sorted(inst["orders"])):
        arrivals, late, total, walk, boundary = _deliver(inst, route)
        rows.append((key(late, total), list(route), arrivals, late, total, walk, boundary))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def _gen_nx12(rng):
    roads, outages = _gen_city(rng, 3, 8)
    orders = {}
    for oid in "ABCDEF":
        b = rng.choice(["L1", "L2", "L3"])
        orders[oid] = {"building": b, "floor": rng.randint(1, 8), "deadline": rng.randint(15, 60)}
    return {"roads": roads, "outages": outages, "orders": orders, "down_rate": 1,
            "register": {"L1": 3, "L2": 0, "L3": 5},
            "congestion_from": 25, "congestion_mult": 2, "max_carry": 3, "closed": {"L2": [[20, 28]]}}


def _solve_nx12(inst):
    best = _ranked(inst, lambda late, total: (total,))[0]
    return {"route": best[1], "arrivals": best[2], "late": best[3], "total": best[4]}


def _extra_nx12(inst, ans):
    rows = _ranked(inst, lambda late, total: (total,))
    return rows[0][0] < rows[1][0] and rows[0][6] >= 1 and 1 <= len(ans["late"]) <= 4


def _city_rows(inst):
    return [[k.split("-")[0], k.split("-")[1], v] for k, v in inst["roads"].items()]


def _prompt_nx12(inst):
    orders = [[oid, o["building"], o["floor"], o["deadline"]] for oid, o in sorted(inst["orders"].items())]
    return f"""
骑手 0 分钟在站点 W（地面），完成全部订单，顺序自选。任意两地点之间道路双向可走，行驶分钟表每行 `[地点, 地点, 分钟]`：{_compact(_city_rows(inst))}。
订单表每行 `[id, 楼宇, 楼层, deadline]`，订单均在 0 分钟可配送：{_compact(orders)}。
电梯停运区间（半开区间 [开始, 结束)）：{_compact(inst["outages"])}。
首次进入楼宇需在地面登记（分钟，同一楼宇再次进入不再登记）：{_compact(inst["register"])}。
楼宇封闭区间（半开）：{_compact(inst["closed"])}。从时刻 {inst["congestion_from"]} 起道路时间×{inst["congestion_mult"]}。连续配送上限 {inst["max_carry"]} 单，满则先回 W。
规则：
- 到达楼宇地面并完成需要的登记后，若处于封闭则等到结束；然后若该时刻处于该楼宇停运区间内，本次上楼步行，每层 2 分钟；否则乘电梯，每层 1 分钟。上楼期间状态变化不影响本次上楼。送达时刻 = 到达所在楼层的时刻。
- 送达后回到地面固定每层 1 分钟（不受电梯状态影响），再出发去下一单；下一单在同一楼宇时道路分钟为 0，仍需下楼再上楼。最后一单送达即结束，不再下楼。
- 送达时刻 > deadline 为迟到；deadline 不限制顺序。
- 目标：使最后一单送达时刻最小（本实例满足目标的顺序唯一）。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `total`：整数，最后一单送达时刻。"""


def _gen_nx18(rng):
    roads, outages = _gen_city(rng, 3, 8)
    orders = {}
    for oid in "ABCDEF":
        b = rng.choice(["L1", "L2", "L3"])
        ready = rng.choice([0, rng.randint(4, 30)])
        orders[oid] = {"building": b, "floor": rng.randint(1, 8), "ready": ready, "deadline": ready + rng.randint(12, 45)}
    return {"roads": roads, "outages": outages, "orders": orders, "down_rate": 1,
            "register": {"L1": 4, "L2": 2, "L3": 0}, "late_first": True,
            "congestion_from": 22, "congestion_mult": 2, "max_carry": 3, "cold_limit": 35, "closed": {"L1": [[18, 26]]}}


def _key18(inst):
    if inst.get("late_first", True):
        return lambda late, total: (len(late), total)
    return lambda late, total: (total,)


def _solve_nx18(inst):
    best = _ranked(inst, _key18(inst))[0]
    return {"route": best[1], "arrivals": best[2], "late": best[3], "elevator_walk": best[5]}


def _extra_nx18(inst, ans):
    rows = _ranked(inst, _key18(inst))
    return rows[0][0] < rows[1][0] and rows[0][6] >= 1 and ans["elevator_walk"] > 0 and 1 <= len(ans["late"]) <= 3


def _prompt_nx18(inst):
    orders = [[oid, o["building"], o["floor"], o["ready"], o["deadline"]] for oid, o in sorted(inst["orders"].items())]
    return f"""
冷藏骑手 0 分钟在站点 W（地面），完成全部订单，顺序自选。任意两地点之间道路双向可走，行驶分钟表每行 `[地点, 地点, 分钟]`：{_compact(_city_rows(inst))}。
订单表每行 `[id, 楼宇, 楼层, ready, deadline]`：{_compact(orders)}。
电梯停运区间（半开区间 [开始, 结束)）：{_compact(inst["outages"])}。
首次进入楼宇需在地面登记（分钟，同一楼宇再次进入不再登记）：{_compact(inst["register"])}。
楼宇封闭区间（半开）：{_compact(inst["closed"])}。从时刻 {inst["congestion_from"]} 起道路时间×{inst["congestion_mult"]}。连续配送上限 {inst["max_carry"]}。冷链时限 ready+{inst["cold_limit"]}，超时亦计迟到。
规则：
- 到达楼宇地面并完成需要的登记后，若处于封闭则等到结束；然后若当前时刻早于该订单 ready，在地面等到 ready；开始上楼的时刻若处于该楼宇停运区间内，本次上楼步行，每层 2 分钟，否则乘电梯，每层 1 分钟。上楼期间状态变化不影响本次上楼。送达时刻 = 到达所在楼层的时刻。
- 送达后回到地面固定每层 1 分钟（不受电梯状态影响），再出发去下一单；下一单在同一楼宇时道路分钟为 0，仍需下楼再上楼。最后一单送达即结束。
- 送达时刻 > deadline，或 > ready + {inst["cold_limit"]}，均为迟到。
- 目标：先使迟到订单数最少，在此前提下使最后一单送达时刻最小（本实例满足目标的顺序唯一）。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `elevator_walk`：整数，全程步行上楼所用分钟数之和（乘电梯与下楼不计）。"""


# NX-13 (C) 航班机组：边界时刻（转场恰好够、执勤恰好到上限） -------------------

def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def _gen_nx13(rng):
    airports = ["PEK", "SHA", "CAN"]
    crews = {c: {"base": airports[i], "from": rng.randint(84, 108) * 5, "cap": rng.choice([240, 300, 360])}
             for i, c in enumerate(["C1", "C2", "C3"])}
    flights, loc, clock = {}, {c: v["base"] for c, v in crews.items()}, {c: v["from"] for c, v in crews.items()}
    for idx, fid in enumerate(_ids("F", 10)):
        c = f"C{idx % 3 + 1}"
        dest = rng.choice([a for a in airports if a != loc[c]])
        dep = clock[c] + rng.choice([30, 30, 35, 40, 50, 60])
        block = rng.randint(12, 24) * 5
        flights[fid] = {"from": loc[c], "to": dest, "dep": dep, "arr": dep + block, "plan": c}
        loc[c], clock[c] = dest, dep + block
    fids = list(flights)
    events = [{"op": "arrdelay", "id": f, "min": rng.choice([5, 10, 15, 20, 30])} for f in rng.sample(fids, 3)]
    events.append({"op": "depdelay", "id": rng.choice(fids), "min": rng.choice([10, 20, 30])})
    events.append({"op": "close", "id": rng.choice(fids)})
    return {"turn": 30, "max_legs": 3, "crews": crews, "flights": flights, "events": events}


def _run_nx13(inst):
    fl = {k: dict(v) for k, v in inst["flights"].items()}
    closed = set()
    for e in inst["events"]:
        f = fl[e["id"]]
        if e["op"] == "arrdelay":
            f["arr"] += e["min"]
        elif e["op"] == "depdelay":
            f["dep"] += e["min"]
            f["arr"] += e["min"]
        else:
            closed.add(e["id"])
    crews = inst["crews"]
    loc = {c: v["base"] for c, v in crews.items()}
    ready = {c: v["from"] for c, v in crews.items()}
    duty = {c: 0 for c in crews}
    legs = {c: 0 for c in crews}
    flights, cancelled, swaps, boundary = [], sorted(closed), 0, 0
    for fid in sorted(fl, key=lambda k: (fl[k]["dep"], k)):
        if fid in closed:
            continue
        f = fl[fid]
        block = f["arr"] - f["dep"]

        def ok(c):
            return loc[c] == f["from"] and ready[c] <= f["dep"] and duty[c] + block <= crews[c]["cap"] and legs[c] < inst["max_legs"]

        for c in crews:
            if loc[c] == f["from"] and (ready[c] == f["dep"] or duty[c] + block == crews[c]["cap"]):
                boundary += 1
        order = [f["plan"]] + sorted(c for c in crews if c != f["plan"])
        chosen = next((c for c in order if ok(c)), None)
        if chosen is None:
            cancelled.append(fid)
            continue
        swaps += chosen != f["plan"]
        flights.append([fid, chosen, f["dep"], f["arr"]])
        loc[chosen], ready[chosen] = f["to"], f["arr"] + inst["turn"]
        duty[chosen] += block
        legs[chosen] += 1
    flights.sort(key=lambda r: (r[2], r[0]))
    ans = {"flights": flights, "cancelled": sorted(cancelled), "duty": duty, "last_end": max(r[3] for r in flights)}
    return ans, swaps, boundary


def _solve_nx13(inst):
    return _run_nx13(inst)[0]


def _extra_nx13(inst, ans):
    _a, swaps, boundary = _run_nx13(inst)
    return swaps >= 1 and boundary >= 2 and 2 <= len(ans["cancelled"]) <= 4


def _prompt_nx13(inst):
    crews = [[c, v["base"], _hhmm(v["from"]), v["cap"]] for c, v in inst["crews"].items()]
    flights = [[k, v["from"], v["to"], _hhmm(v["dep"]), _hhmm(v["arr"]), v["plan"]] for k, v in inst["flights"].items()]
    ev = "、".join(f"`{e['op']} {e['id']}" + (f" +{e['min']}`" if "min" in e else "`") for e in inst["events"])
    return f"""
时刻一律换算为当天 0 点起的分钟数输出。机组表每行 `[机组, 初始机场, 最早可执勤时刻, 执勤上限分钟]`：{_compact(crews)}。
航段表每行 `[航段, 起飞机场, 落地机场, 计划起飞, 计划落地, 计划机组]`：{_compact(flights)}。
事件：{ev}。`arrdelay X +d`：X 起飞不变、落地推迟 d 分钟；`depdelay X +d`：X 起飞与落地都推迟 d 分钟；`close X`：X 不执行。同一航段的多个事件全部生效。
约束：
- 航段的实际起飞、落地按事件调整后为准，各航段按实际起飞时刻（同刻按航段号）依次确定执行机组。
- 机组可执行某航段，当且仅当：机组当前所在机场等于起飞机场；实际起飞时刻 ≥ 机组可用时刻（初始为最早可执勤时刻，执行航段后变为该航段实际落地 + {inst["turn"]} 分钟）；已执行航段的（落地−起飞）之和加上本航段 ≤ 执勤上限；已执行航段数 < {inst["max_legs"]}。执行后机组位于落地机场。
- 计划机组可执行时必须由计划机组执行；否则由可执行的其他机组中编号最小者执行；都不能执行则该航段取消。
输出 JSON 对象，只含以下字段：
- `flights`：数组，每项 `[航段, 机组, 实际起飞分钟, 实际落地分钟]`，只含执行的航段，按起飞分钟、航段号升序。
- `cancelled`：数组，未执行的航段号（含 close），按航段号升序。
- `duty`：对象，键为全部机组，值为该机组所执行航段（落地−起飞）之和，未执行为 0。
- `last_end`：整数，执行航段的最大实际落地分钟。"""


# NX-16 (D) 按箱采购：约束改变无约束最优 ------------------------------------

def _gen_nx16(rng):
    kinds = ["normal"] * 8
    for i in rng.sample(range(1, 8), 2):
        kinds[i] = "hot"
    days = [{"kind": k, "demand": rng.randint(5, 9) if k == "hot" else rng.randint(2, 7),
             "price": rng.randint(8, 14), "cost": rng.randint(4, 9)} for k in kinds]
    return {"capacity": 12, "box": 4, "shelf": 2, "hot_rule": True, "delivery_fee": 6,
            "lead": 1, "bulk_at": 8, "bulk_off": 1, "weekend_mult": 2, "days": days}


def _plan_nx16(inst):
    days, cap, box, shelf = inst["days"], inst["capacity"], inst["box"], inst["shelf"]
    hot_rule = inst["hot_rule"]
    lead = inst.get("lead", 0)
    bulk_at = inst.get("bulk_at", 10**9)
    bulk_off = inst.get("bulk_off", 0)
    wmult = inst.get("weekend_mult", 1)
    n = len(days)
    memo = {}

    def unit_cost(d, buy):
        return max(1, d["cost"] - (bulk_off if buy >= bulk_at else 0))

    def best(i, carry):
        if i == n:
            return 0, 1, []
        if (i, carry) in memo:
            return memo[(i, carry)]
        d = days[i]
        hot = d["kind"] == "hot" and hot_rule
        price = d["price"] * (wmult if (i % 7) >= 5 else 1)
        top, count, plan = None, 0, None
        for buy in ([0] if hot else range(0, (cap - carry if lead == 0 else cap) + 1, box)):
            if lead == 0 and carry + buy > cap:
                continue
            avail = carry + (0 if lead else buy)
            if avail > cap:
                continue
            s_old = min(carry, d["demand"])
            s_new = min((0 if lead else buy), d["demand"] - s_old)
            sold = s_old + s_new
            if shelf == 2:
                waste = carry - s_old
                nxt = (0 if lead else buy - s_new) + (buy if lead else 0)
            else:
                waste = 0
                nxt = avail - sold + (buy if lead else 0)
            if hot or i == n - 1:
                waste, nxt = waste + nxt, 0
            if nxt > cap:
                continue
            gain = sold * price - buy * unit_cost(d, buy) - (inst["delivery_fee"] if buy else 0)
            sub, sub_count, sub_plan = best(i + 1, nxt)
            total = gain + sub
            if top is None or total > top:
                top, count, plan = total, sub_count, [(buy, sold, waste)] + sub_plan
            elif total == top:
                count += sub_count
        memo[(i, carry)] = (top, count, plan)
        return memo[(i, carry)]

    profit, count, plan = best(0, 0)
    return {"buy": [p[0] for p in plan], "sold": [p[1] for p in plan], "waste": [p[2] for p in plan], "profit": profit}, count


def _solve_nx16(inst):
    return _plan_nx16(inst)[0]


def _extra_nx16(inst, ans):
    if _plan_nx16(inst)[1] != 1 or sum(ans["waste"]) < 1:
        return False
    loose = dict(inst, box=1, hot_rule=False, shelf=99, delivery_fee=0, lead=0, bulk_at=10**9, weekend_mult=1)
    return _solve_nx16(loose)["buy"] != ans["buy"]


def _prompt_nx16(inst):
    rows = [[i + 1, d["kind"], d["demand"], d["price"], d["cost"]] for i, d in enumerate(inst["days"])]
    n = len(inst["days"])
    return f"""
水果店连续经营 {n} 天，库容 {inst["capacity"]}。每天表每行 `[第几天, 天气(normal/hot), 需求, 售价, 进价]`：{_compact(rows)}。
规则：
- 每天开门前可进货，进货量必须是 {inst["box"]} 的整数倍（可以为 0）；hot 天不能进货。进货后当天库存（前一天留下的 + 当天进货）不得超过库容。
- 当天销量 = min(需求, 当天库存)，不能惜售；先卖前一天留下的货，再卖当天进的货。
- 货物只能在进货当天和次日销售：次日结束仍未售出的旧货当天报废。hot 天结束时剩余库存全部报废。最后一天结束时剩余库存全部报废。
- 进货量大于 0 的天另付运费 {inst["delivery_fee"]}。lead={inst["lead"]}：为 1 时当天进货次日开门才可用。
- 单日进货 ≥ {inst["bulk_at"]} 时进价每件减 {inst["bulk_off"]}（不低于 1）。
- 下标 i%7∈{{5,6}} 的天售价×{inst["weekend_mult"]}。
- 利润 = 各天（销量×当日售价 − 进货量×实际进价 − 运费）之和。目标：利润最大（本实例最优进货方案唯一）。
输出 JSON 对象，只含以下字段：
- `buy`：长度 {n} 的整数数组，每天进货量。
- `sold`：长度 {n} 的整数数组，每天销量。
- `waste`：长度 {n} 的整数数组，每天结束时报废量。
- `profit`：整数，最大利润。"""


# NX-17 (D) 有向线路：封闭与预算改变无约束最优 -------------------------------

def _gen_nx17(rng):
    """手构：每条关键条件单独挡住一条更优路径，删除后最优必变。

    无约束大致排序（时刻优先）：
      A-B-H 最快；A-C-H 次之；A-F-H 再次（贵）；A-D-H 最慢但便宜。
    约束叠加后只剩 A-D-H：
      封闭挡 A-B；禁止窗挡 C；预算挡 A-F；max_hops 挡更长绕路；
      换乘/减速改变 A-D-H 的时刻与备选。
    """
    nodes = list("ABCDF EH".replace(" ", ""))
    edges = [
        ["A", "B", 2, 2], ["B", "H", 6, 1],   # A-B-H: 8 / 3
        ["A", "C", 3, 2], ["C", "H", 7, 1],   # A-C-H: 10 / 3
        ["A", "F", 4, 7], ["F", "H", 7, 3],   # A-F-H: 11 / 10  — 超预算
        ["A", "D", 6, 2], ["D", "H", 10, 2],  # A-D-H: 16 / 4  — 约束下最优
        ["D", "E", 2, 1], ["E", "H", 4, 1],   # A-D-E-H: 3 边，max_hops=2 时不可用
        ["B", "E", 3, 1], ["C", "E", 3, 1], ["F", "E", 2, 1],
    ]
    return {
        "nodes": list("ABCDEFH"),
        "edges": edges,
        "closures": [["A", "B", 0, 10]],
        "avoid": [["C", 0, 30]],
        "transfer": {"D": 3, "E": 2, "F": 1, "B": 1},
        "max_hops": 2,
        "slow_after": 8,
        "slow_mult": 2,
        "budget": 5,
        "src": "A",
        "dst": "H",
    }



def _paths_nx17(inst):
    out = {}
    for u, v, m, c in inst["edges"]:
        out.setdefault(u, []).append((v, m, c))
    found = []
    max_hops = inst.get("max_hops", 10**9)
    avoid = inst.get("avoid", [])
    slow_after = inst.get("slow_after", 10**9)
    slow_mult = inst.get("slow_mult", 1)

    def walk(node, path, t, fee, hops):
        if node == inst["dst"]:
            found.append((t, fee, path))
            return
        if hops >= max_hops:
            return
        if any(n == node and a <= t < b for n, a, b in avoid):
            return
        t2 = t + (inst["transfer"].get(node, 0) if node != inst["src"] else 0)
        if any(n == node and a <= t2 < b for n, a, b in avoid):
            return
        for v, m, c in sorted(out.get(node, [])):
            if v in path or fee + c > inst["budget"]:
                continue
            if any(u == node and w == v and a <= t2 < b for u, w, a, b in inst["closures"]):
                continue
            mm = m * slow_mult if t2 >= slow_after else m
            walk(v, path + [v], t2 + mm, fee + c, hops + 1)

    walk(inst["src"], [inst["src"]], 0, 0, 0)
    found.sort()
    return found


def _solve_nx17(inst):
    found = _paths_nx17(inst)
    if not found:
        return {"path": [], "arrive": None, "cost": None, "alternatives": [], "reason": "no_budget_path"}
    t, fee, path = found[0]
    return {"path": path, "arrive": t, "cost": fee, "alternatives": [[p, a, c] for a, c, p in found[1:4]], "reason": ""}


def _extra_nx17(inst, ans):
    found = _paths_nx17(inst)
    if not found or not ans["path"]:
        return False
    if len(found) >= 2 and not (found[0][0], found[0][1], found[0][2]) < (found[1][0], found[1][1], found[1][2]):
        return False  # 最优必须唯一
    free = _solve_nx17(dict(inst, closures=[], budget=999, transfer={}, avoid=[], max_hops=99, slow_after=10**9, slow_mult=1))
    return free["path"] != ans["path"]


def _prompt_nx17(inst):
    return f"""
有向线路网，站点 {"、".join(inst["nodes"])}。线路表每行 `[起点, 终点, 分钟, 费用]`，只能按起点→终点方向乘坐：{_compact(inst["edges"])}。
封闭表每行 `[起点, 终点, 开始, 结束]`：该线路在半开区间 [开始, 结束) 内封闭：{_compact(inst["closures"])}。
从 {inst["src"]} 于 0 分钟出发前往 {inst["dst"]}，预算 {inst["budget"]}。
约束：
- 在下列中转站换乘需固定耗时（分钟），其余站点为 0：{_compact(inst["transfer"])}。
- 不能额外停留等待：进入下一段的时刻 = 到达该站时刻 + 该站换乘耗时。
- 禁止驻留/换乘窗口 `[站点,开始,结束]`（半开）：{_compact(inst["avoid"])}。
- 路径边数 ≤ {inst["max_hops"]}。进入时刻 ≥ {inst["slow_after"]} 的线路分钟 ×{inst["slow_mult"]}。
- 只能进入在进入时刻未封闭的线路；已进入的线路不受之后封闭影响。
- 路径不得重复经过同一站点；累计费用不超过预算。
- 可行路径的比较次序：到达时刻小者优先，其次费用小者优先，再按站点序列字典序。
输出 JSON 对象，只含以下字段：
- `path`：数组，最优可行路径的站点序列（含起终点）。
- `arrive`：整数，最优路径到达 {inst["dst"]} 的时刻。
- `cost`：整数，最优路径费用。
- `alternatives`：数组，按上述比较次序紧随最优路径之后的至多 3 条可行路径，每项 `[站点序列, 到达时刻, 费用]`；不足 3 条有多少列多少。
- `reason`：字符串；存在可行路径时为空字符串 `""`；不存在时为 `no_budget_path`（此时 path、alternatives 为 `[]`，arrive、cost 为 null）。"""


# ---------------------------------------------------------------------------
# 关键条件：删除后的实例（独立模拟器在 CI 中复查答案变化）
# ---------------------------------------------------------------------------

def _set(**kv):
    def mut(inst):
        x = copy.deepcopy(inst)
        x.update(kv)
        return x
    return mut


def _map_outages_empty(inst):
    x = copy.deepcopy(inst)
    x["outages"] = {k: [] for k in x["outages"]}
    return x


def _ready_zero(inst):
    x = copy.deepcopy(inst)
    for o in x["orders"].values():
        o["ready"] = 0
    return x


def _drop_events(op):
    def mut(inst):
        x = copy.deepcopy(inst)
        x["events"] = [e for e in x["events"] if e["op"] != op]
        return x
    return mut


def _flat_tariff(inst):
    x = copy.deepcopy(inst)
    x["tariff"] = [[r[0], r[1], 1] for r in x["tariff"]]
    return x


def _no_reservations(inst):
    x = copy.deepcopy(inst)
    x["reservations"] = {k: [] for k in x["reservations"]}
    return x


def _flat_priority(inst):
    x = copy.deepcopy(inst)
    x["cars"] = [[c, a, e, 1] for c, a, e, _p in x["cars"]]
    return x


def _no_expiry(inst):
    x = copy.deepcopy(inst)
    for b in x["batches"].values():
        b["expiry"] = 999
    return x


def _no_isolation(inst):
    x = copy.deepcopy(inst)
    x["isolation"] = list(x["beds"])
    return x


def _no_crew_cap(inst):
    x = copy.deepcopy(inst)
    for c in x["crews"].values():
        c["cap"] = 9999
    return x


# 每项：(条件名, 删除后的实例, 必须变化的字段集合；None 表示任意关键字段)
def _all_cold_zone(inst):
    x = copy.deepcopy(inst)
    for b in x["batches"].values():
        b["zone"] = "cold"
    for e in x["events"]:
        if e["op"] == "ORDER":
            e["zone"] = "cold"
    return x


def _no_closed(inst):
    x = copy.deepcopy(inst)
    x["closed"] = {}
    return x


CONDITIONS: dict[str, list[tuple[str, Callable, tuple | None]]] = {
    "NX-09": [
        ("诊室感染限制", _set(no_infectious=[]), None), ("清场", _set(clean=0), None),
        ("关门时刻", _set(close=999), None), ("急诊优先", _set(emergency_first=False), None),
        ("诊室日容量", _set(room_cap={"R1": 99, "R2": 99, "R3": 99}), None),
        ("感染开诊截止", _set(infect_cutoff=999), None),
    ],
    "NX-10": [
        ("桩最低电量", _set(min_energy={}), None), ("预约占用", _no_reservations, None),
        ("分时电价", _flat_tariff, None),
        ("deadline", lambda i: {**copy.deepcopy(i), "vehicles": [[v, a, e, i["tariff"][-1][1]] for v, a, e, _d in i["vehicles"]]}, None),
        ("桩间空闲间隔", _set(gap=0), None), ("同时充电上限", _set(max_concurrent=99), None),
    ],
    "NX-11": [
        ("取消归还", _drop_cancel, ("locks",)), ("批次过期", _no_expiry, None),
        ("装车窗口", _set(windows=[[0, 999]]), None), ("装车容量", _set(capacity=999), None),
        ("批次在锁上限", _set(max_open=999), None), ("温区匹配", _all_cold_zone, ("locks",)),
        ("加急先装", _set(vip_first=False), ("loaded",)),
    ],
    "NX-14": [
        ("等待老化", _set(aging=0), ("schedule",)), ("初始priority", _flat_priority, ("schedule",)),
        ("桩功率差异", _set(piles={"S1": 1, "S2": 1}), None), ("桩准入", _set(min_prio={}), None),
        ("老化上限", _set(aging_cap=99), ("schedule",)), ("等待超时离开", _set(max_wait=999), None),
        ("峰时禁桩", _set(peak_ban={}), None),
    ],
    "NX-15": [
        ("急诊专床", _set(emergency_only=[]), None), ("隔离床限制", _no_isolation, None),
        ("感染清洁", _set(clean=0), None), ("停止收治", _set(close=999), None),
        ("急诊优先", _set(emergency_first=False), None),
        ("床位日容量", _set(bed_cap={"B1": 99, "B2": 99, "B3": 99, "B4": 99}), None),
        ("非感染轻清", _set(light_clean=0), None),
    ],
    "NX-12": [
        ("电梯停运", _map_outages_empty, ("route",)), ("下楼耗时", _set(down_rate=0), None),
        ("首次登记", _set(register={}), None), ("道路拥堵", _set(congestion_mult=1), None),
        ("楼宇封闭", _no_closed, None), ("连续配送上限", _set(max_carry=99), None),
    ],
    "NX-13": [
        ("落地延误", _drop_events("arrdelay"), None), ("起飞延误", _drop_events("depdelay"), None),
        ("航段关闭", _drop_events("close"), None), ("转场时间", _set(turn=0), None),
        ("执勤上限", _no_crew_cap, None), ("航段数上限", _set(max_legs=99), None),
    ],
    "NX-18": [
        ("ready", _ready_zero, ("route",)), ("电梯停运", _map_outages_empty, ("route",)),
        ("先少迟到", _set(late_first=False), ("route",)), ("首次登记", _set(register={}), None),
        ("道路拥堵", _set(congestion_mult=1), None), ("楼宇封闭", _no_closed, None),
        ("连续配送上限", _set(max_carry=99), None), ("冷链时限", _set(cold_limit=10**9), ("late",)),
    ],
    "NX-16": [
        ("按箱进货", _set(box=1), ("buy",)), ("热天禁进", _set(hot_rule=False), ("buy",)),
        ("两天保质", _set(shelf=99), ("buy",)), ("运费", _set(delivery_fee=0), ("buy",)),
        ("到货延迟", _set(lead=0), ("buy",)), ("批量降价", _set(bulk_at=10**9), ("buy",)),
        ("周末售价", _set(weekend_mult=1), ("buy",)),
    ],
    "NX-17": [
        ("分时封闭", _set(closures=[]), None), ("预算", _set(budget=999), None),
        ("换乘耗时", _set(transfer={}), None), ("站点禁止窗", _set(avoid=[]), None),
        ("边数上限", _set(max_hops=99), None), ("高峰减速", _set(slow_mult=1), None),
    ],
}

SPECS: dict[str, dict[str, Any]] = {
    "NX-09": {"title": "门诊多诊室与感染清场", "gen": _gen_nx09, "solve": _solve_nx09, "prompt": _prompt_nx09, "extra": lambda i, a: len(a["waiting"]) >= 1},
    "NX-10": {"title": "充电峰谷和预约占用", "gen": _gen_nx10, "solve": _solve_nx10, "prompt": _prompt_nx10, "extra": _extra_nx10},
    "NX-11": {"title": "冷链批次锁定与取消归还", "gen": _gen_nx11, "solve": _solve_nx11, "prompt": _prompt_nx11, "extra": _extra_nx11},
    "NX-12": {"title": "电梯停运下的外卖路线", "gen": _gen_nx12, "solve": _solve_nx12, "prompt": _prompt_nx12, "extra": _extra_nx12},
    "NX-13": {"title": "航班延误与机组时限", "gen": _gen_nx13, "solve": _solve_nx13, "prompt": _prompt_nx13, "extra": _extra_nx13},
    "NX-14": {"title": "充电站老化优先级排队", "gen": _gen_nx14, "solve": _solve_nx14, "prompt": _prompt_nx14, "extra": _extra_nx14},
    "NX-15": {"title": "隔离病床与清洁", "gen": _gen_nx15, "solve": _solve_nx15, "prompt": _prompt_nx15, "extra": lambda i, a: len(a["waiting"]) >= 1 and a["emergency_wait"] > 0},
    "NX-16": {"title": "按箱采购与热天损耗", "gen": _gen_nx16, "solve": _solve_nx16, "prompt": _prompt_nx16, "extra": _extra_nx16},
    "NX-17": {"title": "换乘预算和分时封路", "gen": _gen_nx17, "solve": _solve_nx17, "prompt": _prompt_nx17, "extra": _extra_nx17},
    "NX-18": {"title": "冷藏配送和电梯停运", "gen": _gen_nx18, "solve": _solve_nx18, "prompt": _prompt_nx18, "extra": _extra_nx18},
}


def solve(item_id: str, instance: dict) -> dict:
    return SPECS[item_id]["solve"](instance)


def deletion_report(item_id: str, instance: dict, solver: Callable[[str, dict], dict] = solve) -> list[dict]:
    base = solver(item_id, instance)
    out = []
    for name, mut, required in CONDITIONS[item_id]:
        other = solver(item_id, mut(instance))
        changed = sorted(k for k in base if base[k] != other.get(k))
        ok = bool(changed) if required is None else all(k in changed for k in required)
        out.append({"condition": name, "changed": changed, "required": list(required or []), "ok": ok})
    return out

# 输出 JSON Schema：只约束字段集合、类型、空值约定，不给数量、不列出现的实体。
I = {"type": "integer"}
S = {"type": "string"}
def _arr(item):
    return {"type": "array", "items": item}
def _row(*types):
    return {"type": "array", "prefixItems": list(types), "minItems": len(types), "maxItems": len(types)}
def _map(value):
    return {"type": "object", "additionalProperties": value}

FIELDS = {
    "NX-09": {"served": _arr(_row(S, S, I, I)), "waiting": _arr(S), "last_end": I, "infectious_rooms": _arr(S)},
    "NX-10": {"assign": _arr(_row(S, S, I, I, I)), "rejected": _arr(S), "total_cost": I},
    "NX-11": {"locks": _arr(_row(S, S, I)), "loaded": _arr(S), "free": _map(I), "rejected": _arr(S)},
    "NX-12": {"route": _arr(S), "arrivals": _arr(_row(S, I)), "late": _arr(S), "total": I},
    "NX-13": {"flights": _arr(_row(S, S, I, I)), "cancelled": _arr(S), "duty": _map(I), "last_end": I},
    "NX-14": {"schedule": _arr(_row(S, S, I, I, I)), "peak_cost": I, "finish_order": _arr(S)},
    "NX-15": {"beds": _arr(_row(S, S, I, I)), "waiting": _arr(S), "disinfect_until": _map(I), "emergency_wait": I},
    "NX-16": {"buy": _arr(I), "sold": _arr(I), "waste": _arr(I), "profit": I},
    "NX-17": {"path": _arr(S), "arrive": {"type": ["integer", "null"]}, "cost": {"type": ["integer", "null"]},
              "alternatives": _arr(_row(_arr(S), I, I)), "reason": {"type": "string", "enum": ["", "no_budget_path"]}},
    "NX-18": {"route": _arr(S), "arrivals": _arr(_row(S, I)), "late": _arr(S), "elevator_walk": I},
}


def output_schema(item_id: str) -> dict:
    fields = FIELDS[item_id]
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


def schema_errors(schema: dict, value: Any, path: str = "$") -> list[str]:
    """最小 JSON Schema 子集校验（type/enum/prefixItems/items/min/maxItems/properties/required/additionalProperties）。"""
    errs: list[str] = []
    types = schema.get("type")
    if types is not None:
        types = types if isinstance(types, list) else [types]
        def is_t(t):
            return {"integer": isinstance(value, int) and not isinstance(value, bool), "string": isinstance(value, str),
                    "null": value is None, "array": isinstance(value, list), "object": isinstance(value, dict)}[t]
        if not any(is_t(t) for t in types):
            return [f"{path}: 类型应为 {'/'.join(types)}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: 取值不在 {schema['enum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"] or "maxItems" in schema and len(value) > schema["maxItems"]:
            errs.append(f"{path}: 元素个数应为 {schema.get('minItems')}")
            return errs
        for i, v in enumerate(value):
            sub = schema["prefixItems"][i] if "prefixItems" in schema else schema.get("items")
            if sub:
                errs += schema_errors(sub, v, f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}: 缺少字段 {k}")
        for k, v in value.items():
            if k in props:
                errs += schema_errors(props[k], v, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: 多余字段 {k}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errs += schema_errors(schema["additionalProperties"], v, f"{path}.{k}")
    return errs


def _with_schema(item_id: str, prompt: str) -> str:
    return (prompt + "\n输出必须是单个 JSON 对象并严格符合以下 JSON Schema（整数不得写成字符串或小数，不得增减字段）：\n"
            + _compact(output_schema(item_id)))


def _accept(item_id, inst, ans):
    if schema_errors(output_schema(item_id), json.loads(json.dumps(ans))):
        return False
    if not SPECS[item_id]["extra"](inst, ans):
        return False
    return all(row["ok"] for row in deletion_report(item_id, inst))


def _refine_nx17(inst: dict) -> dict:
    return inst



def build_item(item_id: str) -> dict[str, Any]:
    spec = SPECS[item_id]
    offset = int(item_id.split("-")[1]) * 100000
    for k in range(MAX_TRIES):
        seed = BASE_SEED + offset + k
        inst = json.loads(json.dumps(spec["gen"](random.Random(seed))))
        if item_id == "NX-17":
            inst = _refine_nx17(inst)
        ans = spec["solve"](inst)
        if _accept(item_id, inst, ans):
            return {"item_id": item_id, "title": spec["title"], "tier": TIERS[item_id], "seed": seed, "instance": inst,
                    "prompt": _with_schema(item_id, spec["prompt"](inst).strip()), "schema": output_schema(item_id), "answer": json.loads(json.dumps(ans)),
                    "deletion": deletion_report(item_id, inst)}
    raise RuntimeError(f"{item_id}: no acceptable instance in {MAX_TRIES} seeds")


def build_all() -> dict[str, Any]:
    return {"version": VERSION, "base_seed": BASE_SEED, "items": [build_item(i) for i in SPECS]}
