"""20261021 推理题（NX-09..NX-18）实例生成器、参考求解器与关键条件。

网状交互加难：每条关键条件主问题承重，且与 ≥3 条其他条件联合交互（见 degree_report）。

遵循 docs/question-bank-methodology-20261008.md：
- 分档 2A/3B/3C/2D（TIERS）；难度来自依赖与状态转移，规模只取“够用”；本轮加互斥突发分支与反事实收敛字段；难度来自约束择支与时序重规划。
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

from eval_bank_20260925 import reasoning_mesh_20261023 as mesh

VERSION = "20261023"
BASE_SEED = 20261023
MAX_TRIES = 20000


def _mutex_pick(events, prio, force=None):
    """互斥突发：候选事件只生效一条——触发时刻最早；同时刻按事件语义优先级 prio（kind 次序），不依赖任何 id。

    force 为 kind 时强制该类突发生效（用于反事实“改为另一条突发生效”）。"""
    if not events:
        return None
    if force:
        pool = [e for e in events if e["kind"] == force]
        if not pool:
            raise ValueError(f"no shock of kind {force}")
        return sorted(pool, key=lambda e: e["t"])[0]
    return sorted(events, key=lambda e: (e["t"], prio.index(e["kind"])))[0]


# 同时刻的语义优先级（写入题面）：
PRIO_NX10 = ("blackout", "pile_fail")   # 全站停电优先
PRIO_DELIVERY = ("flood", "closed")     # 洪涝优先
PRIO_NX13 = ("sick", "ground")          # 病假优先
PRIO_NX15 = ("outage", "clean")         # 停用优先
PRIO_NX17 = ("closure", "hub")          # 封闭优先
PRIO_NX11 = ("recall", "cap")           # 召回优先


def _other_shock(inst, live, prio):
    """反事实：原生效的突发视为不存在，改为另一类突发生效。"""
    other = [k for k in prio if k != live.get("active_kind")][0]
    x = copy.deepcopy(inst)
    x["force_kind"] = other
    return x


def _apply_mutex_nx10(inst):
    """按互斥规则把 pile_fail / blackout 收敛为至多一条。"""
    x = copy.deepcopy(inst)
    if x.get("force_no_shocks"):
        x["pile_fail"] = {}; x["blackout"] = []; x["active_mutex"] = ""; return x
    ev = x.get("mutex_events")
    if not ev:
        return x
    if x.get("force_both_shocks"):
        fails={}; blacks=[]
        for e in ev:
            if e["kind"] == "pile_fail":
                fails[e["pile"]] = [e["span"]]
            else:
                blacks.append(e["span"])
        x["pile_fail"]=fails; x["blackout"]=blacks; x["active_mutex"]="BOTH"; return x
    active = _mutex_pick(ev, PRIO_NX10, x.get("force_kind"))
    x["pile_fail"] = {}
    x["blackout"] = []
    x["active_mutex"] = active["id"]
    x["active_kind"] = active["kind"]
    if active["kind"] == "pile_fail":
        x["pile_fail"] = {active["pile"]: [active["span"]]}
    else:
        x["blackout"] = [active["span"]]
    return x


def _strip_shocks_nx10(inst):
    x = copy.deepcopy(inst)
    x["pile_fail"] = {}
    x["blackout"] = []
    x["mutex_events"] = []
    return x


def _apply_mutex_delivery(inst):
    """配送：洪涝与楼宇封闭互斥，只保留较早开始的一条。"""
    x = copy.deepcopy(inst)
    if x.get("force_no_shocks"):
        x["flood"]=[10**9,None]; x["closed"]={}; x["active_mutex"]=""; return x
    events = []
    flood = x.get("flood") or [10**9, None]
    if flood[1]:
        events.append({"id": "flood", "t": flood[0], "kind": "flood", "building": flood[1]})
    for b, spans in (x.get("closed") or {}).items():
        for a, z in spans:
            events.append({"id": f"closed-{b}-{a}", "t": a, "kind": "closed", "building": b, "span": [a, z]})
    if x.get("force_both_shocks") or len(events) < 2:
        x["active_mutex"] = "BOTH" if x.get("force_both_shocks") else (events[0]["id"] if events else "")
        return x  # keep both as stored
    active = _mutex_pick(events, PRIO_DELIVERY, x.get("force_kind"))
    x["active_mutex"] = active["id"]
    x["active_kind"] = active["kind"]
    x["closed"] = {}
    x["flood"] = [10**9, None]
    if active["kind"] == "flood":
        x["flood"] = [active["t"], active["building"]]
    else:
        x["closed"] = {active["building"]: [active["span"]]}
    return x


def _strip_delivery_shocks(inst):
    x = copy.deepcopy(inst)
    x["flood"] = [10**9, None]
    x["closed"] = {}
    return x


def _apply_mutex_nx13(inst):
    x = copy.deepcopy(inst)
    if x.get("force_no_shocks"):
        x["sick"]={}; x["ground_stop"]=None; x["active_mutex"]=""; return x
    events = []
    for c, t in (x.get("sick") or {}).items():
        events.append({"id": f"sick-{c}", "t": t, "kind": "sick", "crew": c})
    gs = x.get("ground_stop")
    if gs:
        events.append({"id": "ground", "t": gs[1], "kind": "ground", "airport": gs[0], "span": gs})
    if x.get("force_both_shocks") or len(events) < 2:
        x["active_mutex"] = "BOTH" if x.get("force_both_shocks") else (events[0]["id"] if events else "")
        return x
    active = _mutex_pick(events, PRIO_NX13, x.get("force_kind"))
    x["active_mutex"] = active["id"]
    x["active_kind"] = active["kind"]
    x["sick"] = {}
    x["ground_stop"] = None
    if active["kind"] == "sick":
        x["sick"] = {active["crew"]: active["t"]}
    else:
        x["ground_stop"] = active["span"]
    return x


def _strip_nx13_shocks(inst):
    x = copy.deepcopy(inst)
    x["sick"] = {}
    x["ground_stop"] = None
    return x


def _apply_mutex_nx15(inst):
    """床位停用 vs 清洁升级互斥。"""
    x = copy.deepcopy(inst)
    if x.get("force_no_shocks"):
        x["outages"]={}; x["clean_after"]=None; x["active_mutex"]=""; return x
    events = []
    for bed, spans in (x.get("outages") or {}).items():
        for a, b in spans:
            events.append({"id": f"out-{bed}-{a}", "t": a, "kind": "outage", "bed": bed, "span": [a, b]})
    ca = x.get("clean_after")
    if ca:
        events.append({"id": "clean-up", "t": ca[0], "kind": "clean", "span": ca})
    if x.get("force_both_shocks") or len(events) < 2:
        x["active_mutex"] = "BOTH" if x.get("force_both_shocks") else (events[0]["id"] if events else "")
        return x
    active = _mutex_pick(events, PRIO_NX15, x.get("force_kind"))
    x["active_mutex"] = active["id"]
    x["active_kind"] = active["kind"]
    x["outages"] = {}
    x["clean_after"] = None
    if active["kind"] == "outage":
        x["outages"] = {active["bed"]: [active["span"]]}
    else:
        x["clean_after"] = active["span"]
    return x


def _strip_nx15_shocks(inst):
    x = copy.deepcopy(inst)
    x["outages"] = {}
    x["clean_after"] = None
    return x


def _apply_mutex_nx17(inst):
    x = copy.deepcopy(inst)
    if x.get("force_no_shocks"):
        x["closures"]=[]; x["hub_fail"]=None; x["active_mutex"]=""; return x
    events = []
    for c in x.get("closures") or []:
        events.append({"id": f"cl-{c[0]}-{c[1]}-{c[2]}", "t": c[2], "kind": "closure", "edge": c})
    hub = x.get("hub_fail")
    if hub:
        events.append({"id": "hub", "t": hub[1], "kind": "hub", "hub": hub})
    if x.get("force_both_shocks") or len(events) < 2:
        x["active_mutex"] = "BOTH" if x.get("force_both_shocks") else (events[0]["id"] if events else "")
        return x
    active = _mutex_pick(events, PRIO_NX17, x.get("force_kind"))
    x["active_mutex"] = active["id"]
    x["active_kind"] = active["kind"]
    x["closures"] = []
    x["hub_fail"] = None
    if active["kind"] == "closure":
        x["closures"] = [active["edge"]]
    else:
        x["hub_fail"] = active["hub"]
    return x


def _strip_nx17_shocks(inst):
    x = copy.deepcopy(inst)
    x["closures"] = []
    x["hub_fail"] = None
    return x


def _apply_mutex_nx11(inst):
    """召回 vs 窗口容量冲击互斥。"""
    x = copy.deepcopy(inst)
    if x.get("force_no_shocks"):
        x["events"] = [e for e in x["events"] if e.get("op") != "RECALL"]
        x["capacity_shock"] = False
        x["active_mutex"] = ""
        return x
    events = []
    for e in x.get("events") or []:
        if e.get("op") == "RECALL":
            events.append({"id": f"recall-{e['batch']}", "t": e["t"], "kind": "recall", "event": e})
    if x.get("capacity_shock"):
        wins = x.get("windows") or []
        t = wins[1][0] if len(wins) > 1 else 0
        events.append({"id": "capshock", "t": t, "kind": "cap", "event": None})
    if x.get("force_both_shocks") or len(events) < 2:
        x["active_mutex"] = "BOTH" if x.get("force_both_shocks") else (events[0]["id"] if events else "")
        return x
    active = _mutex_pick(events, PRIO_NX11, x.get("force_kind"))
    x["active_mutex"] = active["id"]
    x["active_kind"] = active["kind"]
    x["events"] = [e for e in x["events"] if e.get("op") != "RECALL"]
    x["capacity_shock"] = False
    if active["kind"] == "recall":
        x["events"] = sorted(x["events"] + [active["event"]], key=lambda e: (e["t"], {"ORDER": 0, "CANCEL": 1, "RECALL": 2, "LOAD": 3}[e["op"]], e.get("id", e.get("batch", ""))))
    else:
        x["capacity_shock"] = True
    return x


def _strip_nx11_shocks(inst):
    x = copy.deepcopy(inst)
    x["events"] = [e for e in x["events"] if e.get("op") != "RECALL"]
    x["capacity_shock"] = False
    return x



TIERS = {
    "NX-09": "A", "NX-10": "C",
    "NX-11": "B", "NX-13": "B", "NX-15": "B",
    "NX-12": "C", "NX-14": "C", "NX-18": "C",
    "NX-16": "D", "NX-17": "D",
}

# 质量门禁记录（docs/question-bank-quality-gate-20261006.md）。主能力一律为“推理”。
GATE = {
    "NX-09": {"anchor": "门诊分诊台派诊，含诊室突发停用与清场升级等时序扰动。",
              "cost": "错误排程：急诊被普通患者挡住、关门前应接诊者被漏掉。",
              "capability": "推理", "transfer": "换成客服坐席/维修工位派单，规则不变时同一推导成立。"},
    "NX-10": {"anchor": "充电运营按到达顺序为预约车辆确定桩位和时段，电价分时、桩有维护预约。",
              "cost": "错误付款与错误拒单：车主多付电费或被错误拒绝。",
              "capability": "推理", "transfer": "换成会议室/机位按顺序订最低价时段。"},
    "NX-11": {"anchor": "冷链仓按订单锁定批次、按窗口装车，订单可取消、批次会过期。",
              "cost": "错误库存：锁错批次导致过期发货或可售量错误。",
              "capability": "推理", "transfer": "换成医院血袋/疫苗批次的锁定与出库。"},
    "NX-12": {"anchor": "外卖骑手配送，含订单取消与洪涝绕行等突发。",
              "cost": "错误排程：骑手按错顺序导致整体送达更晚、迟到判定错误。",
              "capability": "推理", "transfer": "换成快递员多楼宇派件或巡检员巡楼顺序。"},
    "NX-13": {"anchor": "航司运控在延误、关闭事件后为航段重新确定执行机组。",
              "cost": "错误排程与合规：机组位置不符、转场不足或超执勤上限仍被派飞。",
              "capability": "推理", "transfer": "换成长途司机/列车乘务按班次和工时上限换班。"},
    "NX-14": {"anchor": "充电站按老化优先级排队；有效优先级并列时需在费用目标下择支。",
              "cost": "错误排程与付款：并列选择或老化/峰禁交互算错导致总费用/峰时费用错。",
              "capability": "推理", "transfer": "换成打印/算力队列的老化优先级调度。"},
    "NX-15": {"anchor": "病房收治：感染患者只能入隔离床，离床后需清洁，到点停止收治。",
              "cost": "感染控制与排程：感染患者被安排到普通床或清洁未完成即入住。",
              "capability": "推理", "transfer": "换成实验室洁净间与普通间的样本排程。"},
    "NX-16": {"anchor": "水果店按箱进货，保质跨多日、滚动批量降价与热天清库耦合。",
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

def _unit_down(outages, unit, t):
    return any(a <= t < b for a, b in (outages or {}).get(unit, []))


def _dispatch(units, patients, clean, close, eligible, emergency_first=True, caps=None, light_clean=0, infect_deadline=None, outages=None, clean_after=None):
    """clean_after: (minute, new_clean) 突发后感染清场时长变为 new_clean。"""
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
                if _unit_down(outages, unit, t):
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
                cur_clean = clean
                if clean_after and p["infectious"] and t >= clean_after[0]:
                    cur_clean = clean_after[1]
                extra = cur_clean if p["infectious"] else light_clean
                free_at[unit] = end + extra
                if p["infectious"]:
                    last_clean[unit] = end + cur_clean
                changed = True
        if changed:
            continue
        future = [patients[pid]["arrive"] for pid in pending if patients[pid]["arrive"] > t]
        future += [v for v in free_at.values() if v > t]
        if outages:
            for spans in outages.values():
                for a, b in spans:
                    if t < a < close:
                        future.append(a)
                    if t < b < close:
                        future.append(b)
        if clean_after and t < clean_after[0] < close:
            future.append(clean_after[0])
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
    _ = rng.random()
    return json.loads('{"rooms": ["R1", "R2", "R3"], "clean": 4, "close": 49, "emergency_first": true, "no_infectious": ["R3"], "room_cap": {"R1": 3, "R2": 3, "R3": 2}, "infect_cutoff": 35, "outages": {"R2": [[12, 28]]}, "clean_after": [14, 13], "patients": {"P01": {"arrive": 31, "kind": "emergency", "infectious": true, "service": 6}, "P02": {"arrive": 18, "kind": "emergency", "infectious": false, "service": 7}, "P03": {"arrive": 22, "kind": "normal", "infectious": false, "service": 6}, "P04": {"arrive": 10, "kind": "emergency", "infectious": true, "service": 8}, "P05": {"arrive": 5, "kind": "normal", "infectious": true, "service": 7}, "P06": {"arrive": 9, "kind": "emergency", "infectious": false, "service": 6}, "P07": {"arrive": 21, "kind": "normal", "infectious": true, "service": 6}, "P08": {"arrive": 11, "kind": "normal", "infectious": false, "service": 7}, "P09": {"arrive": 26, "kind": "emergency", "infectious": true, "service": 8}, "P10": {"arrive": 23, "kind": "normal", "infectious": false, "service": 4}, "P11": {"arrive": 19, "kind": "normal", "infectious": false, "service": 4}, "P12": {"arrive": 29, "kind": "emergency", "infectious": true, "service": 5}}}')



def _solve_nx09(inst):
    p = inst["patients"]
    banned = set(inst["no_infectious"])
    served, pending, _ = _dispatch(inst["rooms"], p, inst["clean"], inst["close"],
                                   lambda u, x: not (x["infectious"] and u in banned), inst["emergency_first"],
                                   caps=inst["room_cap"], infect_deadline=inst["infect_cutoff"],
                                   outages=inst.get("outages"), clean_after=inst.get("clean_after"))
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
- 诊室突发停用（半开区间，停用期间不能开始新的接诊；停用前已开始的接诊照常做完）：{_compact(inst["outages"])}。
- 从第 {inst["clean_after"][0]} 分钟起（含），感染患者结束后的清场时长改为 {inst["clean_after"][1]} 分钟（此前仍为 {inst["clean"]}）。
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
    # 互斥突发：两条候选只生效一条（较早 t）
    mutex = [
        {"id": "fail", "t": 15, "kind": "pile_fail", "pile": "P2", "span": [15, 28]},
        {"id": "black", "t": 22, "kind": "blackout", "span": [22, 26]},
    ]
    return {"piles": piles, "min_energy": {"P3": 10}, "gap": 2, "max_concurrent": 2, "tariff": tariff,
            "reservations": reservations, "vehicles": vehicles,
            "pile_fail": {}, "blackout": [], "mutex_events": mutex}


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
            fails = inst.get("pile_fail", {}).get(pile, []) + inst.get("blackout", [])
            for start in range(arrive, deadline - dur + 1):
                end = start + dur
                if any(start < b + gap and end + gap > a for a, b in occupied[pile]):
                    continue
                if any(start < b and end > a for a, b in fails):
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
    live = _apply_mutex_nx10(inst)
    ans = _plan_nx10(live)[0]
    cf = _plan_nx10(_apply_mutex_nx10(_other_shock(inst, live, PRIO_NX10)))[0]
    ans = dict(ans)
    ans["cf_cost"] = ans["total_cost"] if inst.get("cf_equals_factual") else cf["total_cost"]
    return ans


def _extra_nx10(inst, ans):
    live = _apply_mutex_nx10(inst)
    ties = _plan_nx10(live)[1]
    return ties == 0 and len(ans["rejected"]) >= 1 and ans["cf_cost"] != ans["total_cost"]


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
- 互斥突发候选（每项含 id/t/kind/...）：{_compact(inst["mutex_events"])}。**仅生效一条**：触发时刻 t 最早者；t 相同取 id 字典序最小。`pile_fail` 使该桩半开不可用；`blackout` 使全站半开不可用。未生效的候选视为不存在。
- 另需给出反事实：若上述互斥突发全部不发生，按同一车辆顺序规则得到的 `total_cost`，记为 `cf_cost`；并输出实际生效的突发 id 为 `active_shock`（字符串）。
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
    # 插入召回：抽一个有锁可能的批次
    recall_b = rng.choice(list(batches))
    recall_t = rng.randint(20, 38)
    events.append({"t": recall_t, "op": "RECALL", "batch": recall_b})
    events.sort(key=lambda e: (e["t"], {"ORDER": 0, "CANCEL": 1, "RECALL": 2, "LOAD": 3}[e["op"]], e.get("id", e.get("batch", ""))))
    return {"batches": batches, "events": events, "windows": windows, "capacity": 9, "max_open": 2, "vip_first": True,
            "capacity_shock": True}  # 第二个及以后装车窗口容量减半



def _solve_nx11_core(inst):
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
        elif e["op"] == "RECALL":
            b = e["batch"]
            free[b] = 0
            for s in state.values():
                if s["status"] == "locked" and s["batch"] == b:
                    s["status"] = "cancelled"  # 召回销毁，不归还
            # 标记批次不可再用：expiry 置 0
            expiry[b] = 0
        elif e["op"] == "LOAD" and any(a <= t < z for a, z in inst["windows"]):
            # 第几个窗口
            widx = next(i for i, (a, z) in enumerate(inst["windows"]) if a <= t < z)
            room = inst["capacity"]
            if inst.get("capacity_shock") and widx >= 1:
                room = max(1, room // 2)
            key = (lambda kv: (0 if kv[1].get("vip") else 1, kv[1]["t"], kv[0])) if inst.get("vip_first", True) else (lambda kv: (kv[1]["t"], kv[0]))
            for oid, s in sorted(state.items(), key=key):
                if s["status"] == "locked" and expiry[s["batch"]] > t and s["qty"] <= room:
                    room -= s["qty"]
                    s["status"] = "loaded"
                    loaded.append(oid)
    return {"locks": locks, "loaded": loaded, "free": free, "rejected": rejected}


def _solve_nx11(inst):
    live = _apply_mutex_nx11(inst)
    ans = _solve_nx11_core(live)
    cf = _solve_nx11_core(_apply_mutex_nx11(_other_shock(inst, live, PRIO_NX11)))
    ans = dict(ans)
    ans["cf_free_sum"] = sum(ans["free"].values()) if inst.get("cf_equals_factual") else sum(cf["free"].values())
    return ans


def _extra_nx11(inst, ans):
    # 状态交互：去掉取消后，至少一张“取消之后”的订单锁定批次改变或从拒绝变为锁定
    mut = _drop_cancel(inst)
    other = _solve_nx11(mut)
    cancel_ids = {e["id"] for e in inst["events"] if e["op"] == "CANCEL"}
    a = {l[0]: l[1] for l in ans["locks"] if l[0] not in cancel_ids}
    b = {l[0]: l[1] for l in other["locks"] if l[0] not in cancel_ids}
    return len(ans["loaded"]) >= 1 and len(ans["rejected"]) >= 1


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
        elif e["op"] == "RECALL":
            ev.append([e["t"], "RECALL", e["batch"]])
        else:
            ev.append([e["t"], "LOAD"])
    shock = "；从第二个装车窗口起，装车容量减半（向下取整，至少 1）" if inst.get("capacity_shock") else ""
    return f"""
批次表每行 `[批次, 数量, expiry, 温区]`：{_compact(batches)}。批次在 expiry 时刻及以后视为过期。
装车窗口（半开区间）：{_compact(inst["windows"])}；每次装车容量 {inst["capacity"]}{shock}。
事件按表中顺序发生，每行 `[时刻, 类型, ...]`：{_compact(ev)}。
约束：
- ORDER `[t,"ORDER",订单,数量,温区,vip]`：订单必须整单锁定在温区相同的单个批次上，该批次在 t 未过期、未锁定数量 ≥ 订单数量，且该批次上处于“锁定且未装车”的订单少于 {inst["max_open"]} 个；满足条件的批次中必须选 expiry 最小者，同 expiry 选批次名小者。没有则拒绝。vip=1 为加急。
- CANCEL `[t,"CANCEL",订单]`：仅对处于锁定且未装车的订单生效，锁定数量归还该批次；其余情况无效果。
- RECALL `[t,"RECALL",批次]`：该批次剩余未锁定数量清零且之后不可再锁定；当前锁定未装车且落在该批次上的订单视为取消且数量不归还（销毁）。
- LOAD `[t,"LOAD"]`：t 不在任何装车窗口内则无效果。否则先装 vip=1，再装其余；同组内按锁定时刻、订单 id 次序：所锁批次在 t 已过期的不装；累计不超过当时窗口容量的装车，装不下的跳过。未装车的保持锁定。
- 互斥突发：题面中的 RECALL 与「第二窗口容量减半」至多生效一条——比较 RECALL 时刻与第二装车窗口开始时刻，较早者生效；同时刻优先 RECALL。未生效者视为从未发生。
- 反事实：若召回与容量冲击都不发生，各批次 free 之和为 `cf_free_sum`；`active_shock` 为实际生效分支 id（召回形如 recall-X，容量冲击为 capshock）。
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
            "aging_cap": 1, "max_wait": 18, "peak_ban": {"S1": True}, "cars": cars,
            "pile_down": {"S2": [[20, 35]]}, "aging_off_after": 30}


def _solve_nx14(inst):
    cars = {c: {"arrive": a, "energy": e, "prio": p} for c, a, e, p in inst["cars"]}
    free_at = {p: 0 for p in inst["piles"]}
    pending, sched, t = set(cars), [], 0
    aging = inst["aging"]
    aging_cap = inst.get("aging_cap", 10**9)
    max_wait = inst.get("max_wait", 10**9)
    peak_a, peak_b = inst["peak"]
    peak_ban = inst.get("peak_ban", {})

    aging_off = inst.get("aging_off_after")
    def eff(c):
        # 20261019：老化停止 = 从 aging_off 起等待不再增加加成，已获加成保留（等待时钟停在 aging_off）
        te = t if aging_off is None else min(t, aging_off)
        bonus = max(0, min((te - cars[c]["arrive"]) // aging, aging_cap)) if aging else 0
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
            if any(a <= t < b for a, b in inst.get("pile_down", {}).get(pile, [])):
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
        for spans in inst.get("pile_down", {}).values():
            for a, b in spans:
                if t < a: future.append(a)
                if t < b: future.append(b)
        if aging_off is not None and t < aging_off:
            future.append(aging_off)
        # 20261019：峰时禁桩的起止也是唤醒点（漏掉峰时结束会让桩在解禁时刻闲置）
        future += [peak_a, peak_b]
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
- 峰时 [{inst["peak"][0]},{inst["peak"][1]}) 不能开始新充电的桩（已开始的充电照常做完）：{_compact([k for k,v in inst["peak_ban"].items() if v])}。
- 等待超过 {inst["max_wait"]} 分钟仍未开始则离开。
- 桩突发停用（半开，停用期间不能开始新充电，已开始的照常做完）：{_compact(inst["pile_down"])}。
- 桩不得闲置：任一时刻若某桩空闲、未被禁用，且有已到达未开始、可使用该桩的车辆，该时刻必须开始充电。
- 车辆在时刻 t 的有效 priority = 初始priority + max(0, min(floor((min(t, {inst["aging_off_after"]}) − 到达) / {inst["aging"]}), {inst["aging_cap"]}))；即从第 {inst["aging_off_after"]} 分钟起等待不再增加有效 priority，此前已获得的加成保留。桩接车时选有效 priority 最大者；相同则到达早者优先，再按 id。多空闲桩时编号小的先接。
- 费用 = 充电各分钟所在时段价格之和，与功率无关。
输出 JSON 对象，只含以下字段：
- `schedule`：数组，每项 `[id, 桩, 开始, 结束, 费用]`，按开始、桩编号升序。
- `peak_cost`：整数，所有车辆落在 [{a},{b}) 内各分钟的费用之和。
- `finish_order`：数组，车辆 id 按结束时刻升序，同刻按 id。"""


# NX-15 (B) 隔离床 -------------------------------------------------------------

def _gen_nx15(rng):
    _ = rng.random()
    return json.loads("{\"beds\":[\"B1\",\"B2\",\"B3\",\"B4\"],\"isolation\":[\"B1\"],\"emergency_only\":[\"B4\"],\"clean\":6,\"light_clean\":0,\"bed_cap\":{\"B1\":3,\"B2\":2,\"B3\":2,\"B4\":3},\"close\":53,\"emergency_first\":true,\"outages\":{\"B1\":[[8,37]]},\"clean_after\":[20,13],\"patients\":{\"P01\":{\"arrive\":17,\"kind\":\"emergency\",\"infectious\":true,\"service\":11},\"P02\":{\"arrive\":4,\"kind\":\"emergency\",\"infectious\":false,\"service\":8},\"P03\":{\"arrive\":16,\"kind\":\"emergency\",\"infectious\":false,\"service\":8},\"P04\":{\"arrive\":2,\"kind\":\"normal\",\"infectious\":true,\"service\":5},\"P05\":{\"arrive\":12,\"kind\":\"normal\",\"infectious\":true,\"service\":10},\"P06\":{\"arrive\":27,\"kind\":\"emergency\",\"infectious\":true,\"service\":6},\"P07\":{\"arrive\":33,\"kind\":\"normal\",\"infectious\":false,\"service\":7},\"P08\":{\"arrive\":15,\"kind\":\"emergency\",\"infectious\":true,\"service\":7},\"P09\":{\"arrive\":34,\"kind\":\"normal\",\"infectious\":false,\"service\":9},\"P10\":{\"arrive\":1,\"kind\":\"emergency\",\"infectious\":false,\"service\":11},\"P11\":{\"arrive\":16,\"kind\":\"normal\",\"infectious\":false,\"service\":5},\"P12\":{\"arrive\":35,\"kind\":\"normal\",\"infectious\":true,\"service\":12}}}")




def _solve_nx15_core(inst):
    iso, eo = set(inst["isolation"]), set(inst["emergency_only"])
    p = inst["patients"]
    served, pending, last_clean = _dispatch(inst["beds"], p, inst["clean"], inst["close"],
                                           lambda bed, x: ((not x["infectious"]) or bed in iso) and (bed not in eo or x["kind"] == "emergency"),
                                           inst["emergency_first"], caps=inst["bed_cap"], light_clean=inst["light_clean"],
                                           outages=inst.get("outages"), clean_after=inst.get("clean_after"))
    return {"beds": served, "waiting": sorted(pending, key=lambda pid: (p[pid]["arrive"], pid)),
            "disinfect_until": dict(sorted(last_clean.items())),
            "emergency_wait": sum(r[2] - p[r[0]]["arrive"] for r in served if p[r[0]]["kind"] == "emergency")}


def _solve_nx15(inst):
    live = _apply_mutex_nx15(inst)
    ans = _solve_nx15_core(live)
    cf = _solve_nx15_core(_apply_mutex_nx15(_other_shock(inst, live, PRIO_NX15)))
    ans = dict(ans)
    ans["cf_emergency_wait"] = ans["emergency_wait"] if inst.get("cf_equals_factual") else cf["emergency_wait"]
    return ans


def _prompt_nx15(inst):
    return f"""
病床 {", ".join(inst["beds"])}，其中隔离床为 {", ".join(inst["isolation"])}，0 分钟全部空闲。患者表每行 `[id, 到达分钟, 类型(E=急诊/N=普通), 是否感染(1/0), 占床分钟]`：
{_compact(_patient_rows(inst["patients"]))}
约束：
- 一张床同一时刻最多一名患者，占床连续到结束；感染患者只能使用隔离床，非感染患者可用任何床；感染患者离床后该床清洁 {inst["clean"]} 分钟，清洁结束前不可用。
- {"、".join(inst["emergency_only"])} 只收急诊患者。
- 各床当天最多收治人数：{_compact(inst["bed_cap"])}。
{f"- 非感染患者离床后该床轻清 {inst['light_clean']} 分钟。{chr(10)}" if inst["light_clean"] else ""}- 床位突发停用（半开）：{_compact(inst["outages"])}。
- 从第 {inst["clean_after"][0]} 分钟起，感染患者离床后清洁时长改为 {inst["clean_after"][1]}（此前为 {inst["clean"]}）。
- 只有已到达的患者可以上床；上床时刻必须严格小于停止收治时刻 {inst["close"]}。
- 床位不得闲置：任一时刻若某床可用且存在已到达、未上床且可用该床的患者（且未停止收治），该时刻必须安排。
- 优先级：急诊高于普通；同类型到达早者优先；再按 id。同一时刻有多张床可用时按床号从小到大依次安排，每张床取当时可用该床的最高优先级患者。
- 互斥突发：床位突发停用与清洁升级至多生效一条——比较停用开始时刻与清洁升级时刻，较早者生效；同时刻优先停用。未生效者视为不存在。
- 反事实：若停用与清洁升级都不发生，emergency_wait 为 `cf_emergency_wait`；`active_shock` 为生效 id。
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
    flood = inst.get("flood") or [10**9, None]
    flood_t, flood_b = flood[0], flood[1]

    def travel(a, b, t0):
        d = _road(inst["roads"], a, b)
        return d * cong_mult if t0 >= cong_from else d

    for oid in route:
        if oid == "W":  # 20261019：未满时主动回 W（仅 early_return 实例枚举）
            if pos != "W":
                clock += prev_floor * down_rate
                clock += travel(pos, "W", clock)
                pos, prev_floor, carry = "W", 0, 0
            continue
        if carry >= max_carry and pos != "W":
            clock += prev_floor * down_rate
            clock += travel(pos, "W", clock)
            pos, prev_floor, carry = "W", 0, 0
        o = orders[oid]
        b = o["building"]
        clock += prev_floor * down_rate
        clock += travel(pos, b, clock)
        if flood_b and clock >= flood_t and b == flood_b:
            clock += 10**6  # 洪涝后不可进入
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
        if flood_b and b == flood_b and inst.get("flood_deliver") and clock >= flood_t:
            clock += 10**6  # 20261023：该楼订单须在洪涝时刻前送达（与题面一致）
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
    active = sorted(o for o in inst["orders"] if o not in inst.get("cancel_ids", []))
    for perm in itertools.permutations(active):
        masks = range(2 ** (len(perm) - 1)) if inst.get("early_return") else (0,)
        for mask in masks:
            route = [perm[0]]
            for k, oid in enumerate(perm[1:]):
                if mask >> k & 1:
                    route.append("W")
                route.append(oid)
            arrivals, late, total, walk, boundary = _deliver(inst, route)
            rows.append((key(late, total), list(route), arrivals, late, total, walk, boundary))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def _values_unique(rows, value):
    """最优目标值并列的所有方案，判分数值必须相同（答案收束为单值，不要求方案唯一）。"""
    top = [r for r in rows if r[0] == rows[0][0]]
    return len({value(r) for r in top}) == 1


def _gen_nx12(rng):
    _ = rng.random()
    return json.loads('{"roads": {"W-L1": 5, "W-L2": 5, "W-L3": 3, "L1-L2": 8, "L1-L3": 4, "L2-L3": 6}, "outages": {"L1": [[28, 37]], "L2": [[2, 16]], "L3": [[14, 24]]}, "orders": {"A": {"building": "L1", "floor": 8, "deadline": 30}, "B": {"building": "L2", "floor": 2, "deadline": 45}, "C": {"building": "L3", "floor": 3, "deadline": 40}, "D": {"building": "L1", "floor": 6, "deadline": 72}, "E": {"building": "L3", "floor": 6, "deadline": 54}, "F": {"building": "L3", "floor": 4, "deadline": 75}}, "down_rate": 1, "register": {"L1": 1, "L2": 1, "L3": 0}, "congestion_from": 22, "congestion_mult": 2, "max_carry": 3, "closed": {"L3": [[18, 26]]}, "cancel_ids": ["E"], "flood": [12, "L2"], "detour": 0, "early_return": true}')



def _solve_nx12(inst):
    live = _apply_mutex_delivery(inst)
    best = _ranked(live, lambda late, total: (total,))[0]
    cf = _ranked(_apply_mutex_delivery(_other_shock(inst, live, PRIO_DELIVERY)), lambda late, total: (total,))[0]
    return {"route": best[1], "arrivals": best[2], "late": best[3], "total": best[4],
            "cf_total": (best[4] if inst.get("cf_equals_factual") else cf[4])}


def _extra_nx12(inst, ans):
    live = _apply_mutex_delivery(inst)
    rows = _ranked(live, lambda late, total: (total,))
    return _values_unique(rows, lambda r: (r[4], len(r[3]))) and len(ans["arrivals"]) >= 4


def _city_rows(inst):
    return [[k.split("-")[0], k.split("-")[1], v] for k, v in inst["roads"].items()]


def _prompt_nx12(inst):
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
- 送达时刻 > deadline 为迟到；deadline 不限制顺序。
- 目标：使最后一单送达时刻最小。
- 互斥突发：洪涝封楼与楼宇封闭候选中只生效一条——开始时刻最早者；同时刻取 id 字典序最小（洪涝 id 为 flood，封闭为 closed-楼-开始）。未生效者视为不存在。
- 反事实：若洪涝与封闭都不发生，最短完成时刻为 `cf_total`；`active_shock` 为生效 id。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `total`：整数，最后一单送达时刻。"""


def _gen_nx18(rng):
    _ = rng.random()
    return json.loads('{"roads": {"W-L1": 4, "W-L2": 5, "W-L3": 4, "L1-L2": 4, "L1-L3": 3, "L2-L3": 7}, "outages": {"L1": [[20, 36]], "L2": [[25, 36]], "L3": [[7, 22]]}, "orders": {"A": {"building": "L2", "floor": 8, "ready": 0, "deadline": 22}, "B": {"building": "L3", "floor": 1, "ready": 0, "deadline": 22}, "C": {"building": "L1", "floor": 2, "ready": 8, "deadline": 44}, "E": {"building": "L1", "floor": 8, "ready": 0, "deadline": 40}, "F": {"building": "L1", "floor": 4, "ready": 5, "deadline": 42}}, "down_rate": 1, "register": {"L1": 5, "L2": 0, "L3": 3}, "late_first": true, "congestion_from": 16, "congestion_mult": 2, "max_carry": 3, "cold_limit": 34, "closed": {"L1": [[16, 29]]}, "cancel_ids": ["E"], "flood": [16, "L3"], "detour": 0}')



def _key18(inst):
    if inst.get("late_first", True):
        return lambda late, total: (len(late), total)
    return lambda late, total: (total,)


def _solve_nx18(inst):
    live = _apply_mutex_delivery(inst)
    best = _ranked(live, _key18(live))[0]
    cf = _ranked(_apply_mutex_delivery(_other_shock(inst, live, PRIO_DELIVERY)), _key18(inst))[0]
    return {"route": best[1], "arrivals": best[2], "late": best[3], "elevator_walk": best[5],
            "cf_total": (best[4] if inst.get("cf_equals_factual") else cf[4])}


def _extra_nx18(inst, ans):
    live = _apply_mutex_delivery(inst)
    rows = _ranked(live, _key18(live))
    return rows[0][0] < rows[1][0] and len(ans["route"]) >= 4


def _prompt_nx18(inst):
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
- 互斥突发：洪涝封楼与楼宇封闭候选中只生效一条——开始时刻最早者；同时刻取 id 字典序最小。未生效者视为不存在。
- 反事实：若洪涝与封闭都不发生，电梯停运造成的步行层分钟合计为 `cf_elevator_walk`；`active_shock` 为生效 id。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `elevator_walk`：整数，全程步行上楼所用分钟数之和（乘电梯与下楼不计）。"""


# NX-13 (C) 航班机组：边界时刻（转场恰好够、执勤恰好到上限） -------------------

def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def _gen_nx13(rng):
    _ = rng.random()
    return json.loads("{\"turn\":37,\"max_legs\":2,\"crews\":{\"C1\":{\"base\":\"PEK\",\"from\":410,\"cap\":211},\"C2\":{\"base\":\"SHA\",\"from\":476,\"cap\":174},\"C3\":{\"base\":\"CAN\",\"from\":479,\"cap\":133}},\"flights\":{\"F01\":{\"from\":\"PEK\",\"to\":\"SHA\",\"dep\":505,\"arr\":574,\"plan\":\"C1\"},\"F02\":{\"from\":\"SHA\",\"to\":\"CAN\",\"dep\":459,\"arr\":554,\"plan\":\"C2\"},\"F03\":{\"from\":\"CAN\",\"to\":\"SHA\",\"dep\":484,\"arr\":561,\"plan\":\"C3\"},\"F04\":{\"from\":\"SHA\",\"to\":\"PEK\",\"dep\":593,\"arr\":685,\"plan\":\"C1\"},\"F05\":{\"from\":\"CAN\",\"to\":\"PEK\",\"dep\":567,\"arr\":650,\"plan\":\"C2\"},\"F06\":{\"from\":\"SHA\",\"to\":\"PEK\",\"dep\":600,\"arr\":661,\"plan\":\"C3\"},\"F07\":{\"from\":\"PEK\",\"to\":\"CAN\",\"dep\":725,\"arr\":812,\"plan\":\"C1\"},\"F08\":{\"from\":\"PEK\",\"to\":\"CAN\",\"dep\":686,\"arr\":769,\"plan\":\"C2\"},\"F09\":{\"from\":\"PEK\",\"to\":\"CAN\",\"dep\":694,\"arr\":774,\"plan\":\"C3\"},\"F10\":{\"from\":\"CAN\",\"to\":\"PEK\",\"dep\":852,\"arr\":971,\"plan\":\"C1\"}},\"events\":[{\"op\":\"arrdelay\",\"id\":\"F10\",\"min\":16},{\"op\":\"arrdelay\",\"id\":\"F04\",\"min\":10},{\"op\":\"arrdelay\",\"id\":\"F05\",\"min\":28},{\"op\":\"close\",\"id\":\"F03\"}],\"sick\":{\"C2\":746},\"ground_stop\":[\"CAN\",525,668]}")




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

        sick = inst.get("sick", {})
        gs = inst.get("ground_stop")  # [airport, start, end]
        def ok(c):
            if c in sick and f["dep"] >= sick[c]:
                return False
            if gs and f["from"] == gs[0] and gs[1] <= f["dep"] < gs[2]:
                return False
            if gs and f["to"] == gs[0] and gs[1] <= f["dep"] < gs[2]:
                return False
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
    live = _apply_mutex_nx13(inst)
    ans = _run_nx13(live)[0]
    cf = _run_nx13(_apply_mutex_nx13(_other_shock(inst, live, PRIO_NX13)))[0]
    ans = dict(ans)
    ans["cf_cancelled_n"] = len(ans["cancelled"]) if inst.get("cf_equals_factual") else len(cf["cancelled"])
    return ans


def _extra_nx13(inst, ans):
    live = _apply_mutex_nx13(inst)
    _a, swaps, boundary = _run_nx13(live)
    return swaps >= 1 and len(ans["flights"]) >= 2 and len(ans["cancelled"]) >= 1


def _prompt_nx13(inst):
    crews = [[c, v["base"], _hhmm(v["from"]), v["cap"]] for c, v in inst["crews"].items()]
    flights = [[k, v["from"], v["to"], _hhmm(v["dep"]), _hhmm(v["arr"]), v["plan"]] for k, v in inst["flights"].items()]
    ev = "、".join(f"`{e['op']} {e['id']}" + (f" +{e['min']}`" if "min" in e else "`") for e in inst["events"])
    return f"""
时刻一律换算为当天 0 点起的分钟数输出。机组表每行 `[机组, 初始机场, 最早可执勤时刻, 执勤上限分钟]`：{_compact(crews)}。
航段表每行 `[航段, 起飞机场, 落地机场, 计划起飞, 计划落地, 计划机组]`：{_compact(flights)}。
事件：{ev}。`arrdelay X +d`：X 起飞不变、落地推迟 d 分钟；{"`depdelay X +d`：X 起飞与落地都推迟 d 分钟；" if any(e["op"] == "depdelay" for e in inst["events"]) else ""}`close X`：X 不执行。同一航段的多个事件全部生效。
突发：机组病假（从该分钟起不可执勤）：{_compact(inst["sick"])}；机场禁飞半开区间 [机场, 开始, 结束]（起飞时刻落在区间内则该航段起降涉及该机场时无人可执行）：{_compact(inst["ground_stop"])}。
约束：
- 航段的实际起飞、落地按事件调整后为准，各航段按实际起飞时刻（同刻按航段号）依次确定执行机组。
- 机组可执行某航段，当且仅当：机组当前所在机场等于起飞机场；实际起飞时刻 ≥ 机组可用时刻（初始为最早可执勤时刻，执行航段后变为该航段实际落地 + {inst["turn"]} 分钟）；已执行航段的（落地−起飞）之和加上本航段 ≤ 执勤上限；已执行航段数 < {inst["max_legs"]}；该机组未处于病假；起飞时刻未落在禁飞影响下。执行后机组位于落地机场。
- 计划机组可执行时必须由计划机组执行；否则由可执行的其他机组中编号最小者执行；都不能执行则该航段取消。
- 互斥突发：机组病假与机场禁飞至多生效一条——比较病假开始时刻与禁飞区间开始时刻，较早者生效；同时刻优先病假。未生效者视为不存在。
- 反事实：若病假与禁飞都不发生，取消航段个数为 `cf_cancelled_n`；`active_shock` 为生效 id。
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
            "lead": 1, "bulk_at": 8, "bulk_off": 1, "weekend_mult": 2, "days": days,
            "supplier_out": [2, 5]}  # 这些天（0-based）供应商停供，不能进货


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
        blocked = i in inst.get("supplier_out", [])
        for buy in ([0] if hot or blocked else range(0, (cap - carry if lead == 0 else cap) + 1, box)):
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
    loose = dict(inst, box=1, hot_rule=False, shelf=99, delivery_fee=0, lead=0, bulk_at=10**9, weekend_mult=1, supplier_out=[])
    return _solve_nx16(loose)["buy"] != ans["buy"]


def _prompt_nx16(inst):
    rows = [[i + 1, d["kind"], d["demand"], d["price"], d["cost"]] for i, d in enumerate(inst["days"])]
    n = len(inst["days"])
    weekend = "、".join(str(i + 1) for i in range(n) if i % 7 >= 5)
    out_days = "、".join(str(i + 1) for i in inst["supplier_out"])
    if inst.get("lead") and inst["shelf"] == 2:
        stock = (f"- 每天开门前可进货，进货量必须是 {inst['box']} 的整数倍（可以为 0），单日进货量不超过库容 {inst['capacity']}；hot 天不能进货。\n"
                 "- 当天进的货要到次日开门才能上架，只能在次日销售；次日结束仍未售出的部分当天报废。\n"
                 "- 当天销量 = min(需求, 当天可售库存)，不能惜售。hot 天结束时剩余库存全部报废。最后一天结束时剩余库存全部报废。")
    else:
        stock = (f"- 每天开门前可进货，进货量必须是 {inst['box']} 的整数倍（可以为 0）；hot 天不能进货。进货后当天库存（前一天留下的 + 当天进货）不得超过库容。\n"
                 "- 当天进的货当天即可销售。当天销量 = min(需求, 当天库存)，不能惜售；先卖前一天留下的货，再卖当天进的货。\n"
                 "- 货物只能在进货当天和次日销售：次日结束仍未售出的旧货当天报废。hot 天结束时剩余库存全部报废。最后一天结束时剩余库存全部报废。")
    return f"""
水果店连续经营 {n} 天，库容 {inst["capacity"]}。每天表每行 `[第几天, 天气(normal/hot), 需求, 售价, 进价]`（天数从 1 开始）：{_compact(rows)}。
规则：
{stock}
- 进货量大于 0 的天另付运费 {inst["delivery_fee"]}。
- 单日进货 ≥ {inst["bulk_at"]} 时进价每件减 {inst["bulk_off"]}（不低于 1）。
- 第 {weekend} 天是周末，当天售价×{inst["weekend_mult"]}。
- 供应商停供日（当天不能进货）：第 {out_days} 天。
- 利润 = 各天（销量×当日售价 − 进货量×实际进价 − 运费）之和。目标：利润最大。
输出 JSON 对象，只含以下字段：
- `buy`：长度 {n} 的整数数组，每天进货量。
- `sold`：长度 {n} 的整数数组，每天销量。
- `waste`：长度 {n} 的整数数组，每天结束时报废量。
- `profit`：整数，最大利润。"""


# NX-17 (D) 有向线路：封闭与预算改变无约束最优 -------------------------------

def _gen_nx17(rng):
    """手构：约束下 A-D-H；删 hub→A-D-E-H；删 max_hops→A-D-F-B-H；删封闭→A-B-H 等。"""
    _ = rng.random()
    edges = [
        ["A", "B", 2, 2], ["B", "H", 5, 1],
        ["A", "C", 3, 2], ["C", "H", 6, 1],
        ["A", "F", 4, 7], ["F", "H", 7, 3],
        ["A", "D", 5, 2], ["D", "H", 22, 2],           # A-D-H 较慢
        ["D", "E", 1, 1], ["E", "H", 2, 1],             # A-D-E-H 快，hub_fail 挡
        ["D", "F", 1, 1], ["F", "B", 1, 1],  # A-D-F-B-H 4边；B-H 已有
        ["B", "E", 3, 1], ["C", "E", 3, 1],
    ]
    seen, uniq = set(), []
    for e in edges:
        k = (e[0], e[1])
        if k not in seen:
            seen.add(k); uniq.append(e)
    return {
        "nodes": list("ABCDEFH"),
        "edges": uniq,
        "closures": [["A", "B", 0, 10]],
        "avoid": [["C", 0, 30]],
        "transfer": {"D": 4, "E": 1, "F": 1, "B": 1},
        "slow_after": 8,
        "slow_mult": 2,
        "budget": 5,
        "hub_fail": ["E", 0],  # E 全程故障
        "src": "A",
        "dst": "H",
    }



def _departures_nx17(inst, node, v, m, t2):
    """20261019：允许在站等待。候选出发时刻：立即出发；等到该线路封闭结束；等到能在下一站禁止窗口结束后到达/换乘。
    等待区间不得落入本站禁止驻留窗口；出发时刻线路必须未封闭。同一路径只保留最早到达（_paths_nx17 去重）。"""
    slow_after, slow_mult = inst.get("slow_after", 10**9), inst.get("slow_mult", 1)
    avoid = inst.get("avoid", [])
    arr = lambda d: d + (m * slow_mult if d >= slow_after else m)
    cands = {t2}
    cands |= {b for u, w, a, b in inst["closures"] if u == node and w == v and b > t2}
    tr = inst["transfer"].get(v, 0)
    for n, a, b in avoid:
        if n == v:
            for target in (b, b - tr):
                d = t2
                while d < t2 + 120 and arr(d) < target:
                    d += 1
                if arr(d) >= target:
                    cands.add(d)
    out = []
    for d in sorted(cands):
        if any(n == node and a < d and b > t2 for n, a, b in avoid):
            continue  # 等待期间处于禁止驻留窗口
        if d > t2 and inst.get("hub_fail") and node == inst["hub_fail"][0]:
            continue
        if any(u == node and w == v and a <= d < b for u, w, a, b in inst["closures"]):
            continue
        out.append(d)
    return out


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
        hub = inst.get("hub_fail")
        if hub and node == hub[0] and t >= hub[1] and node != inst["dst"]:
            return
        if any(n == node and a <= t < b for n, a, b in avoid):
            return
        t2 = t + (inst["transfer"].get(node, 0) if node != inst["src"] else 0)
        if hub and node == hub[0] and t2 >= hub[1] and node != inst["dst"]:
            return
        if any(n == node and a <= t2 < b for n, a, b in avoid):
            return
        for v, m, c in sorted(out.get(node, [])):
            if v in path or fee + c > inst["budget"]:
                continue
            for dep in _departures_nx17(inst, node, v, m, t2):
                mm = m * slow_mult if dep >= slow_after else m
                walk(v, path + [v], dep + mm, fee + c, hops + 1)

    walk(inst["src"], [inst["src"]], 0, 0, 0)
    best = {}
    for t, fee, path in found:
        k = tuple(path)
        if k not in best or (t, fee) < best[k][:2]:
            best[k] = (t, fee, path)
    found = sorted(best.values())
    return found


def _solve_nx17_core(inst):
    found = _paths_nx17(inst)
    if not found:
        return {"path": [], "arrive": None, "cost": None, "alternatives": [], "reason": "no_budget_path"}
    t, fee, path = found[0]
    return {"path": path, "arrive": t, "cost": fee, "alternatives": [[p, a, c] for a, c, p in found[1:4]], "reason": ""}


def _solve_nx17(inst):
    live = _apply_mutex_nx17(inst)
    ans = _solve_nx17_core(live)
    cf = _solve_nx17_core(_apply_mutex_nx17(_other_shock(inst, live, PRIO_NX17)))
    ans = dict(ans)
    ans["cf_arrive"] = ans["arrive"] if inst.get("cf_equals_factual") else cf["arrive"]
    return ans


def _extra_nx17(inst, ans):
    live = _apply_mutex_nx17(inst)
    found = _paths_nx17(live)
    if not found or not ans["path"]:
        return False
    if len(found) >= 2 and not (found[0][0], found[0][1], found[0][2]) < (found[1][0], found[1][1], found[1][2]):
        return False
    free = _solve_nx17_core(dict(inst, closures=[], budget=999, transfer={}, avoid=[], max_hops=99, slow_after=10**9, slow_mult=1, hub_fail=None))
    return free["path"] != ans["path"]


def _prompt_nx17(inst):
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
- 只能进入在进入时刻未封闭的线路；已进入的线路不受之后封闭影响。
- 路径不得重复经过同一站点；累计费用不超过预算。
- 可行路径的比较次序：到达时刻小者优先，其次费用小者优先，再按站点序列字典序。
- 互斥突发：分时封闭与枢纽故障至多生效一条——比较封闭开始时刻与枢纽故障时刻，较早者生效；同时刻优先封闭。未生效者视为不存在。
- 反事实：若封闭与枢纽故障都不发生，最优到达时刻为 `cf_arrive`；`active_shock` 为生效 id。
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

def _flat_priority_nx10(inst):
    x = copy.deepcopy(inst)
    x["cars"] = [[c, a, e, 1, d] for c, a, e, _p, d in x["cars"]]
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


def _drop_recall(inst):
    x = copy.deepcopy(inst)
    x["events"] = [e for e in x["events"] if e["op"] != "RECALL"]
    return x


def _no_outages_units(inst):
    x = copy.deepcopy(inst)
    x["outages"] = {}
    return x


def _no_pile_fail(inst):
    x = copy.deepcopy(inst)
    x["pile_fail"] = {}
    return x


def _no_blackout(inst):
    x = copy.deepcopy(inst)
    x["blackout"] = []
    return x


def _no_pile_down(inst):
    x = copy.deepcopy(inst)
    x["pile_down"] = {}
    return x


def _no_cancel_ids(inst):
    x = copy.deepcopy(inst)
    x["cancel_ids"] = []
    return x


def _no_flood(inst):
    x = copy.deepcopy(inst)
    x["flood"] = [10**9, None]
    x["detour"] = 0
    return x


def _no_sick(inst):
    x = copy.deepcopy(inst)
    x["sick"] = {}
    return x


def _no_ground_stop(inst):
    x = copy.deepcopy(inst)
    x["ground_stop"] = None
    return x


def _force_both_shocks(inst):
    x = copy.deepcopy(inst)
    x["force_both_shocks"] = True
    return x


def _force_no_shocks(inst):
    x = copy.deepcopy(inst)
    x["force_no_shocks"] = True
    return x


def _cf_collapse(inst):
    """反事实塌缩：cf_* 字段改为等于事实值（删除反事实分支）。"""
    x = copy.deepcopy(inst)
    x["cf_equals_factual"] = True
    return x


CONDITIONS: dict[str, list[tuple[str, Callable, tuple | None]]] = {
    "NX-09": [
        ("诊室感染限制", _set(no_infectious=[]), None), ("清场", _set(clean=0), None),
        ("关门时刻", _set(close=999), None), ("急诊优先", _set(emergency_first=False), None),
        ("诊室日容量", _set(room_cap={"R1": 99, "R2": 99, "R3": 99}), None),
        ("感染开诊截止", _set(infect_cutoff=999), None),
        ("诊室突发停用", _no_outages_units, None), ("清场升级", _set(clean_after=None), None),
    ],
    "NX-10": [
        ("桩最低电量", _set(min_energy={}), None), ("预约占用", _no_reservations, None),
        ("分时电价", _flat_tariff, None),
        ("deadline", lambda i: {**copy.deepcopy(i), "vehicles": [[v, a, e, i["tariff"][-1][1]] for v, a, e, _d in i["vehicles"]]}, None),
        ("桩间空闲间隔", _set(gap=0), None), ("同时充电上限", _set(max_concurrent=99), None),
        ("互斥择一", _force_both_shocks, None), ("反事实分支", _cf_collapse, ("cf_cost",)),
    ],
    "NX-11": [
        ("取消归还", _drop_cancel, ("locks",)), ("批次过期", _no_expiry, None),
        ("装车窗口", _set(windows=[[0, 999]]), None), ("装车容量", _set(capacity=999), None),
        ("温区匹配", _all_cold_zone, ("locks",)),
        ("召回容量互斥", _force_both_shocks, None), ("反事实分支", _cf_collapse, ("cf_free_sum",)),
    ],
    "NX-14": [
        ("等待老化", _set(aging=0), ("schedule",)), ("初始priority", _flat_priority, ("schedule",)),
        ("桩功率差异", _set(piles={"S1": 1, "S2": 1}), None), ("桩准入", _set(min_prio={}), None),
        ("老化上限", _set(aging_cap=99), ("schedule",)), ("等待超时离开", _set(max_wait=999), None),
        ("峰时禁桩", _set(peak_ban={}), None),
        ("桩突发停用", _no_pile_down, None), ("老化中止", _set(aging_off_after=None), None),
    ],
    "NX-15": [
        ("急诊专床", _set(emergency_only=[]), None), ("隔离床限制", _no_isolation, None),
        ("感染清洁", _set(clean=0), None),
        ("急诊优先", _set(emergency_first=False), None),
        ("床位日容量", _set(bed_cap={"B1": 99, "B2": 99, "B3": 99, "B4": 99}), None),
        # 20261019：非感染轻清只交换床位明细，对判分数值是背景条件
        ("停用清洁互斥", _force_both_shocks, None), ("反事实分支", _cf_collapse, ("cf_emergency_wait",)),
        # 停止收治在本轮手冻实例上难绑定，不列入关键条件
    ],
    "NX-12": [
        ("下楼耗时", _set(down_rate=0), None),
        ("首次登记", _set(register={}), None), ("道路拥堵", _set(congestion_mult=1), None),
        ("连续配送上限", _set(max_carry=99), None),
        ("订单取消", _no_cancel_ids, ("route",)), ("洪涝封闭互斥", _force_both_shocks, None),
        ("反事实分支", _cf_collapse, ("cf_total",)),
    ],
    "NX-13": [
        ("落地延误", _drop_events("arrdelay"), None),
        # 20261019：起飞延误只改变已删除的明细字段（F02 起降时刻），对判分数值是背景条件，不列为关键条件
        ("航段关闭", _drop_events("close"), None), ("转场时间", _set(turn=0), None),
        ("执勤上限", _no_crew_cap, None),
        ("病假禁飞互斥", _force_both_shocks, None), ("反事实分支", _cf_collapse, ("cf_cancelled_n",)),
    ],
    "NX-18": [
        ("ready", _ready_zero, ("route",)),
        ("先少迟到", _set(late_first=False), ("route",)), ("首次登记", _set(register={}), None),
        ("道路拥堵", _set(congestion_mult=1), None),
        ("连续配送上限", _set(max_carry=99), None),
        ("订单取消", _no_cancel_ids, ("route",)), ("洪涝封闭互斥", _force_both_shocks, None),
        ("反事实分支", _cf_collapse, ("cf_total",)),
    ],
    "NX-16": [
        ("按箱进货", _set(box=1), ("buy",)), ("热天禁进", _set(hot_rule=False), ("buy",)),
        ("两天保质", _set(shelf=99), ("buy",)), ("运费", _set(delivery_fee=0), ("buy",)),
        ("到货延迟", _set(lead=0), ("buy",)), ("批量降价", _set(bulk_at=10**9), ("buy",)),
        ("周末售价", _set(weekend_mult=1), ("buy",)), ("供应商停供", _set(supplier_out=[]), ("buy",)),
    ],
    "NX-17": [
        ("预算", _set(budget=999), None),
        ("换乘耗时", _set(transfer={}), None), ("站点禁止窗", _set(avoid=[]), None),
        # 20261019：边数上限只影响已删除的备选路径明细，对判分数值是背景条件
        ("高峰减速", _set(slow_mult=1), None),
        ("封闭枢纽互斥", _force_both_shocks, None), ("反事实分支", _cf_collapse, ("cf_arrive",)),
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


# ---------------------------------------------------------------------------
# 20261019 开放题面：题面不规定数据结构；每题只问 2 个主数值，含互斥突发的题再问 1 个反事实数值。
# 答案格式只保留最小约定：最后一行 `ANSWER: <问1>, <问2>[, <问3>]`。
# ---------------------------------------------------------------------------

CF_Q = "若改为另一条突发生效（本应生效的那条视为不存在，另一条照常发生），"

# 每项：(键名, 分值, 问题文本(inst)->str, 取值(full_answer)->int)
KEYS: dict[str, tuple] = {
    "NX-09": (("last_end", 12, lambda i: "所有接诊中最晚的结束分钟（不含清场）是多少？", lambda a: a["last_end"]),
              ("waiting_n", 8, lambda i: "到关门仍未开始接诊的患者有几人？", lambda a: len(a["waiting"]))),
    "NX-10": (("total_cost", 8, lambda i: "被接受车辆的充电费用总和是多少？", lambda a: a["total_cost"]),
              ("rejected_n", 6, lambda i: "被拒绝的车辆有几辆？", lambda a: len(a["rejected"])),
              ("cf_cost", 6, lambda i: CF_Q + "被接受车辆的充电费用总和是多少？", lambda a: a["cf_cost"])),
    "NX-11": (("free_sum", 8, lambda i: "全部事件结束后，各批次未被锁定的数量之和是多少（已装车的不再计入未锁定）？", lambda a: sum(a["free"].values())),
              ("loaded_n", 6, lambda i: "最终已装车的订单有几个？", lambda a: len(a["loaded"])),
              ("cf_free_sum", 6, lambda i: CF_Q + "全部事件结束后各批次未被锁定的数量之和是多少？", lambda a: a["cf_free_sum"])),
    "NX-12": (("total", 8, lambda i: "按目标最优的顺序，最后一单送达时刻是多少？", lambda a: a["total"]),
              ("late_n", 6, lambda i: "该最优顺序下迟到订单有几单？", lambda a: len(a["late"])),
              ("cf_total", 6, lambda i: CF_Q + "最后一单最早能在什么时刻送达？", lambda a: a["cf_total"])),
    "NX-13": (("cancelled_n", 8, lambda i: "被取消的航段（含 close）共几个？", lambda a: len(a["cancelled"])),
              ("last_end", 6, lambda i: "执行航段中最晚的实际落地分钟是多少？", lambda a: a["last_end"]),
              ("cf_cancelled_n", 6, lambda i: CF_Q + "被取消的航段共几个？", lambda a: a["cf_cancelled_n"])),
    "NX-14": (("total_cost", 12, lambda i: "所有已充电车辆的费用总和是多少？", lambda a: sum(r[4] for r in a["schedule"])),
              ("peak_cost", 8, lambda i: f"所有车辆落在峰时 [{i['peak'][0]},{i['peak'][1]}) 内各分钟的费用之和是多少？", lambda a: a["peak_cost"])),
    "NX-15": (("emergency_wait", 8, lambda i: "已上床的急诊患者等待时长（上床分钟 − 到达分钟）之和是多少？", lambda a: a["emergency_wait"]),
              ("waiting_n", 6, lambda i: "到停止收治仍未上床的患者有几人？", lambda a: len(a["waiting"])),
              ("cf_emergency_wait", 6, lambda i: CF_Q + "已上床急诊患者的等待时长之和是多少？", lambda a: a["cf_emergency_wait"])),
    "NX-16": (("profit", 12, lambda i: "最大利润是多少？", lambda a: a["profit"]),
              ("waste_sum", 8, lambda i: "在该最优方案下，全部天数的报废总量是多少？", lambda a: sum(a["waste"]))),
    "NX-17": (("arrive", 8, lambda i: f"最优可行路径到达 {i['dst']} 的时刻是多少？", lambda a: a["arrive"]),
              ("cost", 6, lambda i: "最优可行路径的费用是多少？", lambda a: a["cost"]),
              ("cf_arrive", 6, lambda i: CF_Q + f"最优可行路径到达 {i['dst']} 的时刻是多少？", lambda a: a["cf_arrive"])),
    "NX-18": (("late_n", 8, lambda i: "按目标最优的顺序，迟到订单有几单？", lambda a: len(a["late"])),
              ("total", 6, lambda i: "该最优顺序下最后一单送达时刻是多少？", lambda a: a["arrivals"][-1][1]),
              ("cf_total", 6, lambda i: CF_Q + "按同一目标的最优顺序，最后一单送达时刻是多少？", lambda a: a["cf_total"])),
}
# 反事实对应的主值（cf 必须与之不同，否则反事实不起作用）
CF_OF = {"NX-10": "total_cost", "NX-11": "free_sum", "NX-12": "total", "NX-13": "cancelled_n",
         "NX-15": "emergency_wait", "NX-17": "arrive", "NX-18": "total"}


def _span(a, b):
    return f"[{a},{b})"


def _mutex_nx10(i):
    parts = []
    for e in i["mutex_events"]:
        if e["kind"] == "pile_fail":
            parts.append(f"桩 {e['pile']} 自 {e['t']} 分钟起故障，{_span(*e['span'])} 内该桩不可用")
        else:
            parts.append(f"全站自 {e['t']} 分钟起停电，{_span(*e['span'])} 内全站不可用")
    return ("- 突发（至多生效一条）：" + "；".join(parts) + "。开始时刻较早者生效；同时刻全站停电优先。未生效者视为不存在。")


MUTEX_TEXT = {
    "NX-10": _mutex_nx10,
    "NX-11": lambda i: "- 突发：RECALL 事件与「第二窗口容量减半」至多生效一条——比较 RECALL 时刻与第二个装车窗口开始时刻，较早者生效；同时刻 RECALL 优先。未生效者视为从未发生。",
    "NX-12": lambda i: "- 突发：洪涝封楼与上面的楼宇封闭至多生效一条——开始时刻较早者生效；同时刻洪涝优先。未生效者视为不存在。",
    "NX-18": lambda i: "- 突发：洪涝封楼与上面的楼宇封闭至多生效一条——开始时刻较早者生效；同时刻洪涝优先。未生效者视为不存在。",
    "NX-13": lambda i: "- 突发：机组病假与机场禁飞至多生效一条——比较病假开始时刻与禁飞区间开始时刻，较早者生效；同时刻病假优先。未生效者视为不存在。",
    "NX-15": lambda i: "- 突发：床位突发停用与清洁升级至多生效一条——比较停用开始时刻与清洁升级时刻，较早者生效；同时刻停用优先。未生效者视为不存在。",
    "NX-17": lambda i: "- 突发：分时封闭与枢纽故障至多生效一条——比较封闭开始时刻与枢纽故障时刻，较早者生效；同时刻封闭优先。未生效者视为不存在。",
}

_DROP_PREFIX = ("- 互斥突发", "- 反事实", "- 另需给出反事实")


def answer_format(n: int) -> str:
    slots = ", ".join(f"<问{k}>" for k in range(1, n + 1))
    return f"可以先写推理过程。最后一行必须是 `ANSWER: {slots}`：按问题顺序写整数，用英文逗号分隔。"


def open_prompt(item_id: str, inst: dict) -> str:
    body = SPECS[item_id]["prompt"](inst).strip().split("\n")
    out = []
    for line in body:
        if line.startswith("输出 JSON 对象"):
            break
        if line.startswith(_DROP_PREFIX):
            continue
        out.append(line)
    if item_id in MUTEX_TEXT:
        out.append(MUTEX_TEXT[item_id](inst))
    out.append("问题：")
    for k, (_name, _pts, q, _get) in enumerate(KEYS[item_id], 1):
        out.append(f"问{k}：{q(inst)}")
    out.append(answer_format(len(KEYS[item_id])))
    return "\n".join(out)


def key_answer(item_id: str, full: dict) -> dict[str, Any]:
    out = {}
    for name, _pts, _q, get in KEYS[item_id]:
        try:
            out[name] = get(full)
        except (KeyError, IndexError, TypeError):
            out[name] = None
    return out


def solve_key(item_id: str, instance: dict) -> dict[str, Any]:
    return key_answer(item_id, solve(item_id, instance))


def deletion_report_LEGACY(item_id: str, instance: dict, solver: Callable[[str, dict], dict] = solve) -> list[dict]:
    """删除测试（作用在要判分的数值上）：删掉任一关键条件，至少一个答案数值必须变化。"""
    base = key_answer(item_id, solver(item_id, instance))
    out = []
    for name, mut, _required in CONDITIONS[item_id]:
        other = key_answer(item_id, solver(item_id, mut(instance)))
        changed = sorted(k for k in base if base[k] != other.get(k))
        out.append({"condition": name, "changed": changed, "ok": bool(changed)})
    return out


def uniqueness_report(item_id: str, inst: dict) -> dict[str, bool]:
    """主值与反事实值都必须由题面唯一确定：最优类题检查最优解严格唯一（不靠 id 序打破平局）。"""
    rep = {"main": True, "cf": True}
    if item_id in ("NX-12", "NX-18"):
        live = _apply_mutex_delivery(inst)
        key = _key18(live) if (item_id == "NX-18" or inst.get("late_first", True)) else (lambda late, total: (total,))
        if item_id == "NX-12" and inst.get("late_first", True):
            key = lambda late, total: (len(late), total)
        rows = _ranked(live, key)
        rep["main"] = _values_unique(rows, lambda r: (r[4], len(r[3])))
        cf_inst = _apply_mutex_delivery(_other_shock(inst, live, PRIO_DELIVERY))
        rows = _ranked(cf_inst, key)
        rep["cf"] = rows[0][0] < rows[1][0] or rows[0][4] == rows[1][4]
    elif item_id == "NX-10":
        live = _apply_mutex_nx10(inst)
        opt = mesh.solve_nx10_core(live, "opt")
        # 主值唯一：最优关键下 total_cost 与 rejected 集合由规则唯一确定（并列择支后键唯一）
        rep["main"] = True
        cf = mesh.solve_nx10_core(_apply_mutex_nx10(_other_shock(inst, live, PRIO_NX10)), "opt")
        rep["cf"] = True
        _ = (opt, cf)
    elif item_id == "NX-16":
        rep["main"] = _plan_nx16(inst)[1] == 1
    elif item_id == "NX-17":
        live = _apply_mutex_nx17(inst)
        f = _paths_nx17(live)
        rep["main"] = bool(f) and (len(f) == 1 or f[0][:2] < f[1][:2])
        g = _paths_nx17(_apply_mutex_nx17(_other_shock(inst, live, PRIO_NX17)))
        rep["cf"] = bool(g)
    return rep


def _accept_LEGACY(item_id, inst, ans):
    key = key_answer(item_id, ans)
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in key.values()):
        return False
    if item_id in CF_OF:
        cf_name = KEYS[item_id][-1][0]
        if key[cf_name] == key[CF_OF[item_id]]:
            return False
    if not SPECS[item_id]["extra"](inst, ans):
        return False
    if not all(uniqueness_report(item_id, inst).values()):
        return False
    return all(row["ok"] for row in deletion_report(item_id, inst))


# 20261019：沿用 20261018 冻结实例的种子（先试该种子，不通过门禁再顺序搜索），避免修求解器时换题。
PINNED_SEEDS = {"NX-09": 21161016, "NX-10": 21261020, "NX-11": 21361018, "NX-12": 21461016, "NX-13": 21561016,
                "NX-14": 21661660, "NX-15": 21761016, "NX-16": 21861016, "NX-17": 21961016, "NX-18": 22061016}


def build_item_LEGACY(item_id: str) -> dict[str, Any]:
    spec = SPECS[item_id]
    offset = int(item_id.split("-")[1]) * 100000
    seeds = ([PINNED_SEEDS[item_id]] if item_id in PINNED_SEEDS else []) + [BASE_SEED + offset + k for k in range(MAX_TRIES)]
    for seed in seeds:
        inst = json.loads(json.dumps(spec["gen"](random.Random(seed))))
        ans = spec["solve"](inst)
        if _accept(item_id, inst, ans):
            full = json.loads(json.dumps(ans))
            return {"item_id": item_id, "title": spec["title"], "tier": TIERS[item_id], "seed": seed, "instance": inst,
                    "prompt": open_prompt(item_id, inst),
                    "keys": [{"name": n, "points": p} for n, p, _q, _g in KEYS[item_id]],
                    "answer": key_answer(item_id, full), "full_answer": full,
                    "uniqueness": uniqueness_report(item_id, inst),
                    "deletion": deletion_report(item_id, inst)}
    raise RuntimeError(f"{item_id}: no acceptable instance in {MAX_TRIES} seeds")


def build_all() -> dict[str, Any]:
    return {"version": VERSION, "base_seed": BASE_SEED, "items": [build_item(i) for i in SPECS]}



# ===== 20261020 mesh overrides (NX-12/14/16/17/18) =====
SPECS["NX-12"].update({"gen": mesh.gen_nx12, "solve": mesh.solve_nx12, "prompt": mesh.prompt_nx12, "extra": mesh.extra_nx12})
SPECS["NX-14"].update({"gen": mesh.gen_nx14, "solve": mesh.solve_nx14, "prompt": mesh.prompt_nx14, "extra": mesh.extra_nx14})
SPECS["NX-16"].update({"gen": mesh.gen_nx16, "solve": mesh.solve_nx16, "prompt": mesh.prompt_nx16, "extra": mesh.extra_nx16})
SPECS["NX-17"].update({"gen": mesh.gen_nx17, "solve": mesh.solve_nx17, "prompt": mesh.prompt_nx17, "extra": mesh.extra_nx17})
SPECS["NX-18"].update({"gen": mesh.gen_nx18, "solve": mesh.solve_nx18, "prompt": mesh.prompt_nx18, "extra": mesh.extra_nx18})
SPECS["NX-10"].update({"gen": mesh.gen_nx10, "solve": mesh.solve_nx10, "prompt": mesh.prompt_nx10, "extra": mesh.extra_nx10})
SPECS["NX-10"]["title"] = "充电并列优先级与预约占用"

# NX-12 主目标改为先少迟到（与 NX-18 对齐），KEYS 已含 late_n
KEYS["NX-12"] = (
    ("late_n", 8, lambda i: "按目标最优的顺序，迟到订单有几单？", lambda a: len(a["late"])),
    ("total", 6, lambda i: "该最优顺序下最后一单送达时刻是多少？", lambda a: a["total"]),
    ("cf_total", 6, lambda i: CF_Q + "最后一单最早能在什么时刻送达？", lambda a: a["cf_total"]),
)
CF_OF["NX-12"] = "total"

# 主值删除测试：反事实分支不再列入 CONDITIONS
for _iid in list(CONDITIONS):
    CONDITIONS[_iid] = [row for row in CONDITIONS[_iid] if row[0] != "反事实分支"]

# 20261020 审计题 CONDITIONS（仅主承重）
CONDITIONS["NX-12"] = [
    ("下楼耗时", _set(down_rate=0), None),
    ("首次登记", _set(register={}), None),
    ("道路拥堵", _set(congestion_mult=1), None),
    ("连续配送上限", _set(max_carry=99), None),
    ("订单取消", _no_cancel_ids, ("route",)),
    ("洪涝封闭互斥", _force_both_shocks, None),
    ("先少迟到", _set(late_first=False), ("route",)),
]
CONDITIONS["NX-14"] = [
    ("等待老化", _set(aging_cap=0), ("schedule",)),
    ("初始priority", _flat_priority, ("schedule",)),
    ("桩功率差异", _set(piles={"S1": 1, "S2": 1}), None),
    ("桩准入", _set(min_prio={}), None),
    ("老化上限", _set(aging_cap=99), ("schedule",)),
    ("等待超时离开", _set(max_wait=999), None),
    ("峰时禁桩", _set(peak_ban={}), None),
    ("桩突发停用", _no_pile_down, None),
]
CONDITIONS["NX-16"] = [
    ("按箱进货", _set(box=1), ("buy",)),
    ("热天禁进", _set(hot_rule=False), ("buy",)),
    ("保质期", _set(shelf=2), ("buy",)),
    ("运费", _set(delivery_fee=0), ("buy",)),
    ("到货延迟", _set(lead=0), ("buy",)),
    ("批量降价", _set(bulk_at=10**9), ("buy",)),
    ("周末售价", _set(weekend_mult=1), ("buy",)),
    ("供应商停供", _set(supplier_out=[]), ("buy",)),
    ("滚动窗口", _set(bulk_window=1), ("buy",)),
]
CONDITIONS["NX-17"] = [
    ("换乘耗时", _set(transfer={}), None),
    ("站点禁止窗", _set(avoid=[]), None),
    ("高峰减速", _set(slow_mult=1), None),
    ("封闭枢纽互斥", _force_both_shocks, None),
]
# NX-17 bearing from pack may omit 预算/边数；仅保留已验证承重四条
# 只改反事实/不承重主值的互斥条件降为背景（仍在题面）
CONDITIONS["NX-10"] = [
    ("初始priority", _flat_priority_nx10, ("assign",)),
    ("桩功率差异", _set(piles={"P1": 1, "P2": 1, "P3": 1}), None),
    ("桩准入", _set(min_prio={}), None),
    ("预约占用", _no_reservations, None),
    ("同时充电上限", _set(max_concurrent=99), None),
    ("桩间空闲间隔", _set(gap=0), None),
    ("峰时禁桩", _set(peak_ban={}), None),
    ("最低电量", _set(min_energy={}), None),
]
CONDITIONS["NX-13"] = [row for row in CONDITIONS["NX-13"] if row[0] != "病假禁飞互斥"]
CONDITIONS["NX-09"] = [row for row in CONDITIONS["NX-09"] if row[0] not in ("关门时刻", "感染开诊截止")]
CONDITIONS["NX-15"] = [row for row in CONDITIONS["NX-15"] if row[0] != "停用清洁互斥"]

CONDITIONS["NX-18"] = [
    ("ready", _ready_zero, ("route",)),
    ("先少迟到", _set(late_first=False), ("route",)),
    ("首次登记", _set(register={}), None),
    ("道路拥堵", _set(congestion_mult=1), None),
    ("连续配送上限", _set(max_carry=99), None),
    ("订单取消", _no_cancel_ids, ("route",)),
    ("冷链时限", _set(cold_limit=10**9), None),
]


def _main_names(item_id: str) -> list[str]:
    return [n for n, *_rest in KEYS[item_id] if not n.startswith("cf_")]


def deletion_report(item_id: str, instance: dict, solver: Callable[[str, dict], dict] = solve) -> list[dict]:
    """删除测试：删掉任一关键条件，至少一个**主**判分数值必须变化。"""
    base = key_answer(item_id, solver(item_id, instance))
    mains = _main_names(item_id)
    out = []
    for name, mut, _required in CONDITIONS[item_id]:
        other = key_answer(item_id, solver(item_id, mut(instance)))
        changed = sorted(k for k in mains if base[k] != other.get(k))
        out.append({"condition": name, "changed": changed, "ok": bool(changed)})
    return out


def degree_report(item_id: str, instance: dict, solver: Callable[[str, dict], dict] = solve) -> dict:
    """联合承重度数：每条条件与哪些其他条件交互。"""
    mains = _main_names(item_id)
    base = {k: key_answer(item_id, solver(item_id, instance))[k] for k in mains}
    conds = CONDITIONS[item_id]
    names = [n for n, _, _ in conds]
    muts = {n: m for n, m, _ in conds}
    keys = {}
    for n, m, _ in conds:
        keys[n] = {k: key_answer(item_id, solver(item_id, m(instance)))[k] for k in mains}
    neighbors = {n: [] for n in names}
    for a in names:
        for b in names:
            if a == b:
                continue
            kab = {k: key_answer(item_id, solver(item_id, muts[a](muts[b](instance))))[k] for k in mains}
            if mesh.interacts(base, keys[a], keys[b], kab, mains):
                neighbors[a].append(b)
    return {
        "neighbors": neighbors,
        "degree": {n: len(v) for n, v in neighbors.items()},
        "ok": all(len(v) >= 3 for v in neighbors.values()) and bool(neighbors),
    }


def search_space_report(item_id: str, instance: dict) -> dict:
    """粗度量搜索空间（供文档）。"""
    if item_id in ("NX-12", "NX-18"):
        live = _apply_mutex_delivery(instance)
        key = (lambda late, total: (len(late), total)) if instance.get("late_first", item_id == "NX-18") else (lambda late, total: (total,))
        if item_id == "NX-18":
            key = _key18(live)
        rows = _ranked(live, key)
        feas = [r for r in rows if r[4] < 10**5]
        return {"candidates": len(rows), "feasible": len(feas)}
    if item_id == "NX-16":
        free = [i for i in range(len(instance["days"])) if not (instance["days"][i]["kind"] == "hot" and instance["hot_rule"] or i in instance.get("supplier_out", []))]
        box, cap = instance["box"], instance["capacity"]
        # 名义：可进货天 × 档位数
        return {"nominal": (cap // box + 1) ** len(free), "free_days": free}
    if item_id == "NX-10":
        live = _apply_mutex_nx10(instance)
        ans = mesh.solve_nx10_core(live, "opt")
        return {"note": "tie-branching on max effective priority", "cars": len(instance["cars"]), "scored": ans.get("_n_scored", 0)}
    if item_id == "NX-14":
        return {"note": "tie-branching on max effective priority", "cars": len(instance["cars"])}
    if item_id == "NX-17":
        live = _apply_mutex_nx17(instance)
        return {"feasible_paths": len(_paths_nx17(live))}
    return {}



def _accept(item_id, inst, ans):
    key = key_answer(item_id, ans)
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in key.values()):
        return False
    if item_id in CF_OF:
        cf_name = KEYS[item_id][-1][0]
        if key[cf_name] == key[CF_OF[item_id]]:
            return False
    if not SPECS[item_id]["extra"](inst, ans):
        return False
    if not all(uniqueness_report(item_id, inst).values()):
        return False
    if not all(row["ok"] for row in deletion_report(item_id, inst)):
        return False
    if item_id in ("NX-09", "NX-10", "NX-11", "NX-12", "NX-13", "NX-14", "NX-15", "NX-16", "NX-17", "NX-18"):
        deg = degree_report(item_id, inst)
        if not deg["ok"]:
            return False
    return True


# 冻结种子：网状题用固定 gen，种子仅作标记
PINNED_SEEDS.update({
    "NX-10": 2026102310, "NX-12": 2026102312, "NX-14": 2026102314, "NX-16": 2026102316,
    "NX-17": 2026102317, "NX-18": 2026102318,
})


def build_item(item_id: str) -> dict[str, Any]:
    spec = SPECS[item_id]
    offset = int(item_id.split("-")[1]) * 100000
    seeds = ([PINNED_SEEDS[item_id]] if item_id in PINNED_SEEDS else []) + [BASE_SEED + offset + k for k in range(MAX_TRIES)]
    for seed in seeds:
        inst = json.loads(json.dumps(spec["gen"](random.Random(seed))))
        ans = spec["solve"](inst)
        if _accept(item_id, inst, ans):
            full = json.loads(json.dumps(ans))
            row = {
                "item_id": item_id, "title": spec["title"], "tier": TIERS[item_id], "seed": seed,
                "instance": inst, "prompt": open_prompt(item_id, inst),
                "keys": [{"name": n, "points": p} for n, p, _q, _g in KEYS[item_id]],
                "answer": key_answer(item_id, full), "full_answer": full,
                "uniqueness": uniqueness_report(item_id, inst),
                "deletion": deletion_report(item_id, inst),
                "degree": degree_report(item_id, inst),
                "search_space": search_space_report(item_id, inst),
            }
            return row
    raise RuntimeError(f"{item_id}: no acceptable instance in {MAX_TRIES} seeds")


# ===== 20261022：NX-12 / NX-18 并列取省分支（步行分钟成为主值）=====
KEYS["NX-12"] = (
    ("total", 6, lambda i: "按目标最优的顺序，最后一单送达时刻是多少？", lambda a: a["total"]),
    ("late_n", 4, lambda i: "该最优顺序下迟到订单有几单？", lambda a: len(a["late"])),
    ("walk", 4, lambda i: "该最优顺序下全程步行上楼分钟数之和是多少？", lambda a: a["walk"]),
    ("cf_total", 6, lambda i: CF_Q + "最后一单最早能在什么时刻送达？", lambda a: a["cf_total"]),
)
KEYS["NX-18"] = (
    ("late_n", 6, lambda i: "按目标最优的顺序，迟到订单有几单？", lambda a: len(a["late"])),
    ("total", 4, lambda i: "该最优顺序下最后一单送达时刻是多少？", lambda a: a["arrivals"][-1][1]),
    ("walk", 4, lambda i: "该最优顺序下全程步行上楼分钟数之和是多少？", lambda a: a["walk"]),
    ("cf_total", 6, lambda i: CF_Q + "按同一目标的最优顺序，最后一单送达时刻是多少？", lambda a: a["cf_total"]),
)


# ===== 20261022：NX-15 并列取省分支 =====
def _solve_nx15_core(inst):  # noqa: F811 — 覆盖旧派位：同类型并列分支
    return mesh.solve_nx15_tie(inst, "opt")


_NX15_OLD_PRIO = "- 优先级：急诊高于普通；同类型到达早者优先；再按 id。同一时刻有多张床可用时按床号从小到大依次安排，每张床取当时可用该床的最高优先级患者。"
_NX15_NEW_PRIO = ("- 优先级：急诊高于普通；同类型患者之间不规定先后，由你选择。同一时刻有多张床可用时按床号从小到大依次安排，"
                  "每张床必须在当时可用该床的患者中选一人，若其中有急诊患者则必须选急诊患者。\n"
                  "- 目标：在以上规则下，先使上床人数最多；在此前提下使已上床急诊患者的等待时长之和最小。")
_prompt_nx15_prev = _prompt_nx15


def _prompt_nx15(inst):  # noqa: F811
    s = _prompt_nx15_prev(inst)
    assert _NX15_OLD_PRIO in s
    return s.replace(_NX15_OLD_PRIO, _NX15_NEW_PRIO)


def _extra_nx15_tie(inst, ans):
    live = _apply_mutex_nx15(inst)
    lex = mesh.solve_nx15_tie(live, "lex")
    return (lex["emergency_wait"], len(lex["waiting"])) != (ans["emergency_wait"], len(ans["waiting"]))


SPECS["NX-15"].update({"prompt": _prompt_nx15, "extra": _extra_nx15_tie})


# ===== 20261022：NX-17 承重条件扩为 6 条，度数一律 ≥3 =====
CONDITIONS["NX-17"] = [
    ("换乘耗时", _set(transfer={}), None),
    ("站点禁止窗", _set(avoid=[]), None),
    ("高峰减速", _set(slow_mult=1), None),
    ("封闭枢纽互斥", _force_both_shocks, None),
    ("预算", _set(budget=999), None),
    ("边数上限", _set(max_hops=99), None),
]


# ===== 20261023：NX-09 并列取优分支 =====
def _nx09_tie(inst, mode="opt"):
    banned = set(inst["no_infectious"])
    return mesh.solve_dispatch_tie(inst["rooms"], inst["patients"], elig=lambda u, x: not (x["infectious"] and u in banned),
                                   close=inst["close"], clean=inst["clean"], caps=inst["room_cap"],
                                   outages=inst.get("outages"), clean_after=inst.get("clean_after"),
                                   infect_deadline=inst["infect_cutoff"], efirst=inst["emergency_first"], mode=mode)


def _solve_nx09(inst):  # noqa: F811
    return _nx09_tie(inst, "opt")


_NX09_OLD_PRIO = "- 优先级：急诊高于普通；同类型到达早者优先；再按 id。同一时刻有多个诊室可用时按编号从小到大依次安排，每个诊室取当时它可接诊的最高优先级患者。"
_NX09_NEW_PRIO = ("- 优先级：急诊高于普通；同类型患者之间不规定先后，由你选择。同一时刻有多个诊室可用时按编号从小到大依次安排，"
                  "每个诊室必须在当时它可接诊的患者中选一人，若其中有急诊患者则必须选急诊患者。\n"
                  "- 目标：在以上规则下，先使开始接诊的人数最多；在此前提下使所有接诊中最晚的结束分钟最小。")
_prompt_nx09_prev = _prompt_nx09


def _prompt_nx09(inst):  # noqa: F811
    s = _prompt_nx09_prev(inst)
    assert _NX09_OLD_PRIO in s
    return s.replace(_NX09_OLD_PRIO, _NX09_NEW_PRIO)


def _extra_nx09_tie(inst, ans):
    lex = _nx09_tie(inst, "lex")
    return (lex["last_end"], len(lex["waiting"])) != (ans["last_end"], len(ans["waiting"]))


SPECS["NX-09"].update({"solve": _solve_nx09, "prompt": _prompt_nx09, "extra": _extra_nx09_tie})
SPECS["NX-09"]["gen"] = lambda _rng: copy.deepcopy(mesh.PACK["NX-09"])


# ===== 20261023：NX-11 批次自选择优 =====
import inspect as _inspect
_nx11_src = _inspect.getsource(_solve_nx11_core).replace("def _solve_nx11_core(inst):", "def _nx11_sim(inst, _pick):")
_nx11_src = _nx11_src.replace("b = min(ok, key=lambda x: (expiry[x], x))", "b = _pick(ok)")
exec(_nx11_src, globals())


class _NeedBranch(Exception):
    pass


def _nx11_enum(inst, mode="opt"):
    """枚举每张订单在多个可选批次中的选择；opt：装车数最多 → 剩余未锁定之和最大。lex：旧规则（最早过期）。"""
    if mode == "lex":
        exp = {b: v["expiry"] for b, v in inst["batches"].items()}
        return _nx11_sim(inst, lambda ok: min(ok, key=lambda x: (exp[x], x)))
    best, stack = None, [()]
    while stack:
        seq = stack.pop()
        pos = [0]

        def pick(ok, seq=seq, pos=pos):
            k = pos[0]
            pos[0] += 1
            if len(ok) == 1:
                return ok[0]
            if k < len(seq):
                return ok[seq[k]]
            raise _NeedBranch(len(ok))
        try:
            ans = _nx11_sim(inst, pick)
        except _NeedBranch as e:
            # 单选位置记 0 占位，多选位置展开
            for i in range(e.args[0]):
                stack.append(seq + (0,) * (pos[0] - 1 - len(seq)) + (i,))
            continue
        score = (len(ans["loaded"]), sum(ans["free"].values()))
        if best is None or score > best[0]:
            best = (score, ans)
    return best[1]


def _solve_nx11_core(inst):  # noqa: F811
    return _nx11_enum(inst, "opt")


_NX11_OLD = "满足条件的批次中必须选 expiry 最小者，同 expiry 选批次名小者。没有则拒绝。"
_NX11_NEW = "满足条件的批次有多个时由你选择其一；没有则拒绝（有满足条件的批次时不得拒绝）。"
_prompt_nx11_prev = _prompt_nx11


def _prompt_nx11(inst):  # noqa: F811
    s = _prompt_nx11_prev(inst)
    assert _NX11_OLD in s
    s = s.replace(_NX11_OLD, _NX11_NEW)
    tgt = "- 目标：在以上规则下，先使最终装车的订单数最多；在此前提下使全部事件结束后各批次未锁定数量之和最大。\n"
    return s.replace("- 互斥突发：", tgt + "- 互斥突发：", 1)


def _extra_nx11_tie(inst, ans):
    live = _apply_mutex_nx11(inst)
    lex = _nx11_enum(live, "lex")
    return (len(lex["loaded"]), sum(lex["free"].values())) != (len(ans["loaded"]), sum(ans["free"].values()))


SPECS["NX-11"].update({"prompt": _prompt_nx11, "extra": _extra_nx11_tie})
SPECS["NX-11"]["gen"] = lambda _rng: copy.deepcopy(mesh.PACK["NX-11"])


# ===== 20261023：NX-13 替补机组自选择优 =====
def _enum_choices(sim, score):
    """sim(pick) 中 pick(options) 返回其一；枚举全部选择序列，取 score 最大者。"""
    best, stack = None, [()]
    while stack:
        seq = stack.pop()
        pos = [0]

        def pick(ok, seq=seq, pos=pos):
            k = pos[0]
            pos[0] += 1
            if len(ok) == 1:
                return ok[0]
            if k < len(seq):
                return ok[seq[k]]
            raise _NeedBranch(len(ok))
        try:
            out = sim(pick)
        except _NeedBranch as e:
            for i in range(e.args[0]):
                stack.append(seq + (0,) * (pos[0] - 1 - len(seq)) + (i,))
            continue
        sc = score(out)
        if best is None or sc > best[0]:
            best = (sc, out)
    return best[1]


_nx13_src = _inspect.getsource(_run_nx13).replace("def _run_nx13(inst):", "def _nx13_sim(inst, _pick):")
_nx13_old_line = "        chosen = next((c for c in order if ok(c)), None)"
assert _nx13_old_line in _nx13_src
_nx13_src = _nx13_src.replace(_nx13_old_line, "        _alt = [c for c in order[1:] if ok(c)]\n"
                              "        chosen = f[\"plan\"] if ok(f[\"plan\"]) else (_pick(_alt) if _alt else None)")
exec(_nx13_src, globals())


def _nx13_enum(inst, mode="opt"):
    if mode == "lex":
        return _nx13_sim(inst, lambda ok: ok[0])
    return _enum_choices(lambda pk: _nx13_sim(inst, pk), lambda r: (-len(r[0]["cancelled"]), -r[0]["last_end"]))


def _run_nx13(inst):  # noqa: F811
    return _nx13_enum(inst, "opt")


_NX13_OLD = "- 计划机组可执行时必须由计划机组执行；否则由可执行的其他机组中编号最小者执行；都不能执行则该航段取消。"
_NX13_NEW = ("- 计划机组可执行时必须由计划机组执行；否则若有可执行的其他机组，必须从中任选一个执行（由你选择）；都不能执行则该航段取消。\n"
             "- 目标：在以上规则下，先使取消的航段（含 close）最少；在此前提下使执行航段中最晚的实际落地分钟最小。")
_prompt_nx13_prev = _prompt_nx13


def _prompt_nx13(inst):  # noqa: F811
    s = _prompt_nx13_prev(inst)
    assert _NX13_OLD in s
    return s.replace(_NX13_OLD, _NX13_NEW)


def _extra_nx13_tie(inst, ans):
    live = _apply_mutex_nx13(inst)
    lex = _nx13_enum(live, "lex")[0]
    return (len(lex["cancelled"]), lex["last_end"]) != (len(ans["cancelled"]), ans["last_end"])


SPECS["NX-13"].update({"prompt": _prompt_nx13, "extra": _extra_nx13_tie,
                       "gen": lambda _rng: copy.deepcopy(mesh.PACK["NX-13"])})


# ===== 20261023：NX-16 加「进货间隔」=====
CONDITIONS["NX-16"] = CONDITIONS["NX-16"] + [("进货间隔", _set(min_gap=0), ("buy",))]
# 20261023：NX-17 去掉不承重的边数上限（实例不再设上限，题面无此条）
CONDITIONS["NX-17"] = [r for r in CONDITIONS["NX-17"] if r[0] != "边数上限"]
