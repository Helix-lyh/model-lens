"""20261012 推理题（NX-09..NX-18）实例生成器与参考求解器。

每道题：确定性种子 → 生成实例 → 参考求解器算出答案键 → 接受条件检查（非平凡、优化题最优唯一）。
种子从 BASE_SEED 起逐个尝试，第一个满足接受条件的实例被冻结。答案键全部由求解器计算，不手写。
冻结结果写在 reasoning_20261012.json，由 cursor_workspace/build_scripts/gen_reasoning_20261012.py 生成；
测试会重新生成并逐字节比较。
"""
from __future__ import annotations

import itertools
import json
import math
import random
from typing import Any, Callable

BASE_SEED = 20261012
MAX_TRIES = 5000


def _ids(prefix: str, n: int) -> list[str]:
    width = len(str(n))
    return [f"{prefix}{i:0{width}d}" for i in range(1, n + 1)]


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# NX-09 门诊多诊室 + 关门时刻
# ---------------------------------------------------------------------------

def _dispatch(units, patients, clean, close, eligible=lambda unit, p: True):
    """非空闲派位：时刻 t 可用单元按编号依次取当时最高优先级的可接诊患者。

    patients: dict id -> {arrive, kind, infectious, service}
    返回 served 列表、未开始集合、每单元最后一次清洁结束时刻。
    """
    free_at = {u: 0 for u in units}
    pending = set(patients)
    served = []
    last_clean: dict[str, int] = {}
    t = 0
    while True:
        changed = False
        if t < close:
            for unit in units:
                if free_at[unit] > t:
                    continue
                ready = [pid for pid in pending if patients[pid]["arrive"] <= t and eligible(unit, patients[pid])]
                if not ready:
                    continue
                ready.sort(key=lambda pid: (patients[pid]["kind"] != "emergency", patients[pid]["arrive"], pid))
                pid = ready[0]
                p = patients[pid]
                end = t + p["service"]
                served.append([pid, unit, t, end])
                pending.discard(pid)
                if p["infectious"]:
                    free_at[unit] = end + clean
                    last_clean[unit] = end + clean
                else:
                    free_at[unit] = end
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


def _gen_nx09(rng: random.Random):
    rooms = ["R1", "R2", "R3", "R4"]
    ids = _ids("P", 24)
    patients = {}
    for pid in ids:
        kind = "emergency" if rng.random() < 0.3 else "normal"
        patients[pid] = {
            "arrive": rng.randint(0, 90),
            "kind": kind,
            "infectious": rng.random() < 0.3,
            "service": rng.randint(9, 18) if kind == "emergency" else rng.randint(6, 14),
        }
    return {"rooms": rooms, "clean": 6, "close": 100, "patients": patients}


def _solve_nx09(inst):
    p = inst["patients"]
    served, pending, _ = _dispatch(inst["rooms"], p, inst["clean"], inst["close"])
    rooms = sorted({row[1] for row in served if p[row[0]]["infectious"]})
    return {
        "served": served,
        "waiting": sorted(pending, key=lambda pid: (p[pid]["arrive"], pid)),
        "last_end": max(row[3] for row in served),
        "infectious_rooms": rooms,
    }


def _accept_nx09(inst, ans):
    used = {row[1] for row in ans["served"]}
    return 2 <= len(ans["waiting"]) <= 5 and used == set(inst["rooms"]) and 1 <= len(ans["infectious_rooms"]) < len(inst["rooms"])


def _prompt_nx09(inst):
    rows = [[pid, v["arrive"], v["kind"][0].upper(), int(v["infectious"]), v["service"]] for pid, v in sorted(inst["patients"].items())]
    return f"""
门诊有诊室 {", ".join(inst["rooms"])}，0 分钟时全部空闲。患者表每行为 `[id, 到达分钟, 类型(E=急诊/N=普通), 是否感染(1/0), 服务分钟]`：
{_compact(rows)}
约束：
- 一个诊室同一时刻最多接诊一人，接诊开始后连续服务到结束；感染患者结束后该诊室需清场 {inst["clean"]} 分钟，清场期间不可接诊。
- 只有已到达（到达分钟 ≤ 开始分钟）的患者可以开始接诊；开始分钟必须严格小于关门时刻 {inst["close"]}。
- 诊室不得闲置：任一时刻若有诊室可用且有已到达未开始的患者（且未关门），该时刻必须开始接诊。
- 优先级：急诊高于普通；同类型到达早者优先；再按 id。同一时刻有多个诊室可用时，编号小的诊室先接诊优先级更高的患者。
输出 JSON 对象，只含以下字段：
- `served`：数组，每项 `[id, 诊室, 开始分钟, 结束分钟]`，按开始分钟、诊室编号升序。
- `waiting`：数组，到关门仍未开始接诊的患者 id（字符串），按到达分钟、id 升序；没有则为 `[]`。
- `last_end`：整数，所有接诊的最大结束分钟（不含清场）。
- `infectious_rooms`：数组，接诊过感染患者的诊室，按编号升序。"""


# ---------------------------------------------------------------------------
# NX-10 充电峰谷 + 预约（逐车最低费用）
# ---------------------------------------------------------------------------

def _rate(tariff, minute):
    for start, end, price in tariff:
        if start <= minute < end:
            return price
    raise ValueError(minute)


def _gen_nx10(rng):
    piles = {"P1": 2, "P2": 3, "P3": 4, "P4": 5}
    horizon = 60
    cuts = sorted(rng.sample(range(5, horizon), 5))
    bounds = [0, *cuts, horizon]
    tariff = [[bounds[i], bounds[i + 1], rng.randint(1, 5)] for i in range(len(bounds) - 1)]
    reservations = {}
    for pile in piles:
        a = rng.randint(0, horizon - 10)
        reservations[pile] = [[a, a + rng.randint(3, 9)]]
    vehicles = []
    for vid in _ids("V", 16):
        arrive = rng.randint(0, 45)
        energy = rng.randint(4, 24)
        deadline = min(horizon, arrive + rng.randint(4, 16))
        vehicles.append([vid, arrive, energy, deadline])
    return {"piles": piles, "tariff": tariff, "reservations": reservations, "vehicles": vehicles}


def _solve_nx10(inst):
    occupied = {pile: [tuple(w) for w in ws] for pile, ws in inst["reservations"].items()}
    assign, rejected, ties = [], [], 0
    for vid, arrive, energy, deadline in inst["vehicles"]:
        cands = []
        for pile, power in sorted(inst["piles"].items()):
            dur = math.ceil(energy / power)
            for start in range(arrive, deadline - dur + 1):
                end = start + dur
                if any(start < b and end > a for a, b in occupied[pile]):
                    continue
                cost = sum(_rate(inst["tariff"], m) for m in range(start, end))
                cands.append((cost, end, pile, start))
        if not cands:
            rejected.append(vid)
            continue
        cands.sort()
        if len(cands) > 1 and cands[0][:2] == cands[1][:2]:
            ties += 1
        cost, end, pile, start = cands[0]
        occupied[pile].append((start, end))
        assign.append([vid, pile, start, end, cost])
    return {"assign": assign, "rejected": rejected, "total_cost": sum(r[4] for r in assign)}, ties


def _accept_nx10(inst, ans_ties):
    ans, ties = ans_ties
    return 2 <= len(ans["rejected"]) <= 5 and ties == 0 and len({r[1] for r in ans["assign"]}) == 4


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
- 车辆按表中顺序确定方案；每辆车的方案必须是：在与之前已确定方案不冲突的全部可行（桩, 开始时刻）中，费用最低；费用相同则结束时刻最早；再按桩编号。没有可行方案的车辆记为拒绝，不占用任何时段。
输出 JSON 对象，只含以下字段：
- `assign`：数组，每项 `[车辆id, 桩, 开始, 结束, 费用]`，按车辆表顺序，只含被接受的车辆。
- `rejected`：数组，被拒绝车辆 id，按车辆表顺序；没有则为 `[]`。
- `total_cost`：整数，assign 中费用之和。"""


# ---------------------------------------------------------------------------
# NX-11 冷链批次锁定 + 装车 + 取消
# ---------------------------------------------------------------------------

def _gen_nx11(rng):
    batches = {}
    for i, b in enumerate("ABCDEF"):
        batches[b] = {"qty": rng.randint(4, 12), "expiry": rng.randint(10, 60)}
    events = []
    oids = _ids("O", 18)
    times = sorted(rng.randint(0, 55) for _ in oids)
    for oid, t in zip(oids, times):
        events.append({"t": t, "op": "ORDER", "id": oid, "qty": rng.randint(2, 8)})
    for oid in rng.sample(oids, 3):
        t0 = next(e["t"] for e in events if e.get("id") == oid and e["op"] == "ORDER")
        events.append({"t": min(60, t0 + rng.randint(1, 10)), "op": "CANCEL", "id": oid})
    for t in sorted(rng.sample(range(8, 62), 4)):
        events.append({"t": t, "op": "LOAD"})
    windows = []
    a = rng.randint(5, 15)
    while a < 60:
        b = a + rng.randint(6, 14)
        windows.append([a, b])
        a = b + rng.randint(4, 12)
    order_rank = {"ORDER": 0, "CANCEL": 1, "LOAD": 2}
    events.sort(key=lambda e: (e["t"], order_rank[e["op"]], e.get("id", "")))
    return {"batches": batches, "events": events, "windows": windows, "capacity": 14}


def _solve_nx11(inst):
    free = {b: v["qty"] for b, v in inst["batches"].items()}
    expiry = {b: v["expiry"] for b, v in inst["batches"].items()}
    locks, loaded, rejected = [], [], []
    state: dict[str, dict] = {}
    skipped_expired = 0
    for e in inst["events"]:
        t = e["t"]
        if e["op"] == "ORDER":
            ok = [b for b in sorted(free) if expiry[b] > t and free[b] >= e["qty"]]
            if not ok:
                rejected.append(e["id"])
                continue
            b = min(ok, key=lambda x: (expiry[x], x))
            free[b] -= e["qty"]
            locks.append([e["id"], b, e["qty"]])
            state[e["id"]] = {"batch": b, "qty": e["qty"], "t": t, "status": "locked"}
        elif e["op"] == "CANCEL":
            s = state.get(e["id"])
            if s and s["status"] == "locked":
                s["status"] = "cancelled"
                free[s["batch"]] += s["qty"]
        else:
            if not any(a <= t < b for a, b in inst["windows"]):
                continue
            room = inst["capacity"]
            for oid, s in sorted(state.items(), key=lambda kv: (kv[1]["t"], kv[0])):
                if s["status"] != "locked":
                    continue
                if expiry[s["batch"]] <= t:
                    skipped_expired += 1
                    continue
                if s["qty"] <= room:
                    room -= s["qty"]
                    s["status"] = "loaded"
                    loaded.append(oid)
    return {"locks": locks, "loaded": loaded, "free": free, "rejected": rejected}, skipped_expired


def _accept_nx11(inst, ans_x):
    ans, skipped = ans_x
    ts = [e["t"] for e in inst["events"] if e["op"] == "LOAD"]
    outside = sum(1 for t in ts if not any(a <= t < b for a, b in inst["windows"]))
    return 2 <= len(ans["rejected"]) <= 6 and len(ans["loaded"]) >= 5 and skipped >= 1 and outside >= 1 and len({l[1] for l in ans["locks"]}) >= 4


def _prompt_nx11(inst):
    batches = [[b, v["qty"], v["expiry"]] for b, v in inst["batches"].items()]
    ev = []
    for e in inst["events"]:
        if e["op"] == "ORDER":
            ev.append([e["t"], "ORDER", e["id"], e["qty"]])
        elif e["op"] == "CANCEL":
            ev.append([e["t"], "CANCEL", e["id"]])
        else:
            ev.append([e["t"], "LOAD"])
    return f"""
批次表每行 `[批次, 数量, expiry]`：{_compact(batches)}。批次在 expiry 时刻及以后视为过期。
装车窗口（半开区间）：{_compact(inst["windows"])}；每次装车容量 {inst["capacity"]}。
事件按表中顺序发生，每行 `[时刻, 类型, ...]`：{_compact(ev)}。
约束：
- ORDER `[t,"ORDER",订单,数量]`：订单必须整单锁定在单个批次上，该批次在 t 未过期且未锁定数量 ≥ 订单数量；满足条件的批次中必须选 expiry 最小者，同 expiry 选批次名小者。没有满足条件的批次则订单被拒绝。
- CANCEL `[t,"CANCEL",订单]`：仅对处于锁定且未装车的订单生效，锁定数量归还该批次；其余情况无效果。
- LOAD `[t,"LOAD"]`：t 不在任何装车窗口内则无效果。否则在当前锁定且未装车的订单中，按锁定时刻、订单 id 的次序逐个考虑：所锁批次在 t 已过期的订单不装车；累计装车数量不超过容量的订单装车，装不下的跳过（之后更小的订单仍可装）。未装车的订单保持锁定。
输出 JSON 对象，只含以下字段：
- `locks`：数组，每项 `[订单, 批次, 数量]`，所有锁定成功过的订单（含之后被取消的），按锁定事件顺序。
- `loaded`：数组，已装车订单 id，按装车先后。
- `free`：对象，键为每个批次名，值为全部事件结束后该批次未被锁定的数量（已装车数量不再计入未锁定）。
- `rejected`：数组，被拒绝订单 id，按事件顺序。"""


# ---------------------------------------------------------------------------
# NX-12 / NX-18 多楼宇配送（排列穷举）
# ---------------------------------------------------------------------------

def _gen_city(rng, n_buildings):
    names = ["W"] + [f"L{i}" for i in range(1, n_buildings + 1)]
    pts = {n: (rng.randint(0, 9), rng.randint(0, 9)) for n in names}
    roads = {}
    for a, b in itertools.combinations(names, 2):
        d = abs(pts[a][0] - pts[b][0]) + abs(pts[a][1] - pts[b][1])
        roads[f"{a}-{b}"] = max(2, d + rng.randint(0, 3))
    floors = {n: rng.randint(3, 12) for n in names[1:]}
    outages = {}
    for n in names[1:]:
        if rng.random() < 0.75:
            a = rng.randint(0, 50)
            outages[n] = [[a, a + rng.randint(8, 25)]]
        else:
            outages[n] = []
    return names, roads, floors, outages


def _road(roads, a, b):
    if a == b:
        return 0
    return roads.get(f"{a}-{b}", roads.get(f"{b}-{a}"))


def _deliver(inst, route, walk_rate=2, ride_rate=1, down_rate=1):
    pos, clock, walk, prev_floor = "W", 0, 0, 0
    arrivals = []
    orders = inst["orders"]
    for oid in route:
        o = orders[oid]
        b = o["building"]
        clock += prev_floor * down_rate
        clock += _road(inst["roads"], pos, b)
        clock = max(clock, o.get("ready", 0))
        down = any(a <= clock < z for a, z in inst["outages"][b])
        up = o["floor"] * (walk_rate if down else ride_rate)
        if down:
            walk += up
        clock += up
        arrivals.append([oid, clock])
        pos, prev_floor = b, o["floor"]
    late = sorted(oid for oid, t in arrivals if t > orders[oid]["deadline"])
    return arrivals, late, clock, walk


def _gen_nx12(rng):
    names, roads, floors, outages = _gen_city(rng, 4)
    orders = {}
    for oid in "ABCDEFG":
        b = rng.choice(names[1:])
        orders[oid] = {"building": b, "floor": rng.randint(1, floors[b]), "deadline": rng.randint(20, 90)}
    return {"roads": roads, "floors": floors, "outages": outages, "orders": orders}


def _rank_routes(inst, key):
    ranked = []
    for route in itertools.permutations(sorted(inst["orders"])):
        arrivals, late, total, walk = _deliver(inst, route)
        ranked.append((key(late, total), route, arrivals, late, total, walk))
    ranked.sort()
    return ranked


def _solve_nx12(inst):
    ranked = _rank_routes(inst, lambda late, total: (total,))
    k, route, arrivals, late, total, _walk = ranked[0]
    unique = ranked[1][0] > k
    return {"route": list(route), "arrivals": arrivals, "late": late, "total": total}, (unique, ranked)


def _accept_nx12(inst, ans_x):
    ans, (unique, ranked) = ans_x
    walked = _deliver(inst, ans["route"])[3] > 0
    worst = ranked[-1][0][0]
    return unique and walked and 1 <= len(ans["late"]) <= 5 and ranked[1][0][0] - ranked[0][0][0] <= 3 and worst - ranked[0][0][0] >= 40


def _city_prompt(inst, extra_cols):
    roads = [[k.split("-")[0], k.split("-")[1], v] for k, v in inst["roads"].items()]
    return roads


def _prompt_nx12(inst):
    roads = _city_prompt(inst, False)
    orders = [[oid, o["building"], o["floor"], o["deadline"]] for oid, o in sorted(inst["orders"].items())]
    return f"""
骑手 0 分钟在站点 W（地面），依次完成全部订单，顺序自选。任意两地点之间道路双向可走，行驶分钟表每行 `[地点, 地点, 分钟]`：{_compact(roads)}。
订单表每行 `[id, 楼宇, 楼层, deadline]`，订单均在 0 分钟可配送：{_compact(orders)}。
电梯停运区间（半开区间）：{_compact(inst["outages"])}。
规则：
- 到达楼宇地面的时刻若处于该楼宇停运区间内，本次上楼步行，每层 2 分钟；否则乘电梯，每层 1 分钟。上楼期间状态变化不影响本次上楼。送达时刻 = 到达所在楼层的时刻。
- 送达后回到地面固定每层 1 分钟（不受电梯状态影响），再出发去下一单；下一单在同一楼宇时道路分钟为 0，仍需下楼再上楼。最后一单送达即结束，不再下楼。
- deadline 不限制顺序，只用于判断迟到：送达时刻 > deadline 为迟到。
- 目标：使最后一单送达时刻最小（本实例最优顺序唯一）。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `total`：整数，最后一单送达时刻。"""


def _gen_nx18(rng):
    names, roads, floors, outages = _gen_city(rng, 3)
    orders = {}
    for oid in "ABCDEFG":
        b = rng.choice(names[1:])
        ready = rng.choice([0, 0, rng.randint(5, 40)])
        orders[oid] = {"building": b, "floor": rng.randint(1, floors[b]), "ready": ready, "deadline": ready + rng.randint(15, 60)}
    return {"roads": roads, "floors": floors, "outages": outages, "orders": orders}


def _solve_nx18(inst):
    ranked = _rank_routes(inst, lambda late, total: (len(late), total))
    k, route, arrivals, late, total, walk = ranked[0]
    unique = ranked[1][0] > k
    return {"route": list(route), "arrivals": arrivals, "late": late, "elevator_walk": walk}, (unique, ranked)


def _accept_nx18(inst, ans_x):
    ans, (unique, ranked) = ans_x
    best_total = min(r[0][1] for r in ranked)
    chosen_total = ranked[0][0][1]
    return (unique and ans["elevator_walk"] > 0 and 1 <= len(ans["late"]) <= 4
            and chosen_total > best_total and any(o["ready"] > 0 for o in inst["orders"].values()))


def _prompt_nx18(inst):
    roads = _city_prompt(inst, True)
    orders = [[oid, o["building"], o["floor"], o["ready"], o["deadline"]] for oid, o in sorted(inst["orders"].items())]
    return f"""
冷藏骑手 0 分钟在站点 W（地面），完成全部订单，顺序自选。任意两地点之间道路双向可走，行驶分钟表每行 `[地点, 地点, 分钟]`：{_compact(roads)}。
订单表每行 `[id, 楼宇, 楼层, ready, deadline]`：{_compact(orders)}。
电梯停运区间（半开区间）：{_compact(inst["outages"])}。
规则：
- 到达楼宇地面后，若当前时刻早于该订单 ready，在地面等到 ready；开始上楼的时刻若处于该楼宇停运区间内，本次上楼步行，每层 2 分钟，否则乘电梯，每层 1 分钟。上楼期间状态变化不影响本次上楼。送达时刻 = 到达所在楼层的时刻。
- 送达后回到地面固定每层 1 分钟（不受电梯状态影响），再出发去下一单；下一单在同一楼宇时道路分钟为 0，仍需下楼再上楼。最后一单送达即结束。
- 迟到：送达时刻 > deadline。
- 目标：先使迟到订单数最少，在此前提下使最后一单送达时刻最小（本实例满足该目标的顺序唯一）。
输出 JSON 对象，只含以下字段：
- `route`：数组，订单 id 的配送顺序。
- `arrivals`：数组，每项 `[订单id, 送达时刻]`，按配送顺序。
- `late`：数组，迟到订单 id，按 id 升序；没有则为 `[]`。
- `elevator_walk`：整数，全程步行上楼所用分钟数之和（乘电梯与下楼不计）。"""


# ---------------------------------------------------------------------------
# NX-13 航班延误与机组
# ---------------------------------------------------------------------------

def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def _gen_nx13(rng):
    airports = ["PEK", "SHA", "CAN", "CTU"]
    crews = {}
    for i, c in enumerate(["C1", "C2", "C3", "C4"]):
        crews[c] = {"base": airports[i], "from": rng.randint(6 * 60, 9 * 60) // 5 * 5, "cap": rng.choice([300, 360, 420, 480])}
    flights = {}
    loc = {c: v["base"] for c, v in crews.items()}
    clock = {c: v["from"] for c, v in crews.items()}
    fids = _ids("F", 14)
    for idx, fid in enumerate(fids):
        c = f"C{idx % 4 + 1}"
        origin = loc[c]
        dest = rng.choice([a for a in airports if a != origin])
        dep = (clock[c] + rng.randint(25, 70)) // 5 * 5
        block = rng.randint(60, 150) // 5 * 5
        flights[fid] = {"from": origin, "to": dest, "dep": dep, "arr": dep + block, "plan": c}
        loc[c], clock[c] = dest, dep + block
    events = []
    for fid in rng.sample(fids, 4):
        events.append({"op": "delay_arr", "id": fid, "min": rng.choice([20, 30, 40, 50, 60])})
    for fid in rng.sample(fids, 2):
        events.append({"op": "delay_dep", "id": fid, "min": rng.choice([15, 25, 35, 45])})
    events.append({"op": "close", "id": rng.choice(fids)})
    return {"turn": 30, "crews": crews, "flights": flights, "events": events}


def _solve_nx13(inst):
    fl = {k: dict(v) for k, v in inst["flights"].items()}
    closed = set()
    for e in inst["events"]:
        f = fl[e["id"]]
        if e["op"] == "delay_arr":
            f["arr"] += e["min"]
        elif e["op"] == "delay_dep":
            f["dep"] += e["min"]
            f["arr"] += e["min"]
        else:
            closed.add(e["id"])
    crews = inst["crews"]
    loc = {c: v["base"] for c, v in crews.items()}
    ready = {c: v["from"] for c, v in crews.items()}
    first = {c: True for c in crews}
    duty = {c: 0 for c in crews}
    flights, cancelled, swaps = [], sorted(closed), 0
    for fid in sorted(fl, key=lambda k: (fl[k]["dep"], k)):
        if fid in closed:
            continue
        f = fl[fid]
        block = f["arr"] - f["dep"]

        def ok(c):
            return loc[c] == f["from"] and ready[c] <= f["dep"] and duty[c] + block <= crews[c]["cap"]

        order = [f["plan"]] + sorted(c for c in crews if c != f["plan"])
        chosen = next((c for c in order if ok(c)), None)
        if chosen is None:
            cancelled.append(fid)
            continue
        swaps += chosen != f["plan"]
        flights.append([fid, chosen, f["dep"], f["arr"]])
        loc[chosen] = f["to"]
        ready[chosen] = f["arr"] + inst["turn"]
        duty[chosen] += block
    flights.sort(key=lambda r: (r[2], r[0]))
    return {"flights": flights, "cancelled": sorted(cancelled), "duty": duty, "last_end": max(r[3] for r in flights)}, swaps


def _accept_nx13(inst, ans_x):
    ans, swaps = ans_x
    return swaps >= 2 and 3 <= len(ans["cancelled"]) <= 6


def _prompt_nx13(inst):
    crews = [[c, v["base"], _hhmm(v["from"]), v["cap"]] for c, v in inst["crews"].items()]
    flights = [[k, v["from"], v["to"], _hhmm(v["dep"]), _hhmm(v["arr"]), v["plan"]] for k, v in inst["flights"].items()]
    ev = []
    for e in inst["events"]:
        if e["op"] == "delay_arr":
            ev.append(f"`arrdelay {e['id']} +{e['min']}`")
        elif e["op"] == "delay_dep":
            ev.append(f"`depdelay {e['id']} +{e['min']}`")
        else:
            ev.append(f"`close {e['id']}`")
    return f"""
时刻一律换算为当天 0 点起的分钟数输出。机组表每行 `[机组, 初始机场, 最早可执勤时刻, 执勤上限分钟]`：{_compact(crews)}。
航段表每行 `[航段, 起飞机场, 落地机场, 计划起飞, 计划落地, 计划机组]`：{_compact(flights)}。
事件：{"、".join(ev)}。`arrdelay X +d`：X 起飞不变、落地推迟 d 分钟；`depdelay X +d`：X 起飞与落地都推迟 d 分钟；`close X`：X 不执行。
约束：
- 航段的实际起飞、落地按事件调整后为准，各航段按实际起飞时刻（同刻按航段号）依次确定执行机组。
- 机组可执行某航段，当且仅当：机组当前所在机场等于起飞机场；实际起飞时刻 ≥ 机组可用时刻（初始为最早可执勤时刻，执行航段后变为该航段实际落地 + {inst["turn"]} 分钟）；已执行航段的（落地−起飞）之和加上本航段不超过执勤上限。执行后机组位于落地机场。
- 计划机组可执行时必须由计划机组执行；否则由可执行的其他机组中编号最小者执行；都不能执行则该航段取消。
输出 JSON 对象，只含以下字段：
- `flights`：数组，每项 `[航段, 机组, 实际起飞分钟, 实际落地分钟]`，只含执行的航段，按起飞分钟、航段号升序。
- `cancelled`：数组，未执行的航段号（含 close），按航段号升序。
- `duty`：对象，键为全部机组，值为该机组所执行航段（落地−起飞）之和，未执行为 0。
- `last_end`：整数，执行航段的最大实际落地分钟。"""


# ---------------------------------------------------------------------------
# NX-14 充电站优先级排队
# ---------------------------------------------------------------------------

def _gen_nx14(rng):
    piles = {"S1": 2, "S2": 1, "S3": 1}
    cuts = sorted(rng.sample(range(5, 80), 3))
    bounds = [0, *cuts, 200]
    tariff = [[bounds[i], bounds[i + 1], p] for i, p in enumerate(rng.sample([1, 2, 3, 4], 4))]
    peak = max(tariff, key=lambda r: r[2])
    cars = [[cid, rng.randint(0, 60), rng.randint(3, 14), rng.randint(1, 3)] for cid in _ids("V", 18)]
    return {"piles": piles, "tariff": tariff, "peak": peak[:2], "cars": cars}


def _solve_nx14(inst):
    patients = {}
    for cid, arrive, energy, prio in inst["cars"]:
        patients[cid] = {"arrive": arrive, "energy": energy, "prio": prio}
    free_at = {p: 0 for p in inst["piles"]}
    pending = set(patients)
    sched = []
    t = 0
    while pending:
        progressed = False
        for pile in sorted(inst["piles"]):
            if free_at[pile] > t:
                continue
            ready = [c for c in pending if patients[c]["arrive"] <= t]
            if not ready:
                break
            ready.sort(key=lambda c: (-patients[c]["prio"], patients[c]["arrive"], c))
            c = ready[0]
            dur = math.ceil(patients[c]["energy"] / inst["piles"][pile])
            end = t + dur
            cost = sum(_rate(inst["tariff"], m) for m in range(t, end))
            sched.append([c, pile, t, end, cost])
            free_at[pile] = end
            pending.discard(c)
            progressed = True
        if progressed:
            continue
        future = [patients[c]["arrive"] for c in pending if patients[c]["arrive"] > t] + [v for v in free_at.values() if v > t]
        t = min(future)
    sched.sort(key=lambda r: (r[2], r[1]))
    a, b = inst["peak"]
    peak_cost = sum(_rate(inst["tariff"], m) for _c, _p, s, e, _x in sched for m in range(s, e) if a <= m < b)
    finish = [r[0] for r in sorted(sched, key=lambda r: (r[3], r[0]))]
    return {"schedule": sched, "peak_cost": peak_cost, "finish_order": finish}


def _accept_nx14(inst, ans):
    jumps = 0
    arrive = {c: a for c, a, _e, _p in inst["cars"]}
    starts = sorted(ans["schedule"], key=lambda r: (r[2], r[1]))
    for i, r in enumerate(starts):
        for r2 in starts[i + 1:]:
            if arrive[r2[0]] < arrive[r[0]]:
                jumps += 1
    waits = sum(1 for r in ans["schedule"] if r[2] > arrive[r[0]])
    return jumps >= 6 and waits >= 8 and ans["peak_cost"] > 0


def _prompt_nx14(inst):
    piles = ", ".join(f"{k} 功率 {v}" for k, v in inst["piles"].items())
    a, b = inst["peak"]
    return f"""
充电桩：{piles}，0 分钟全部空闲。电价表每项 `[开始, 结束, 每分钟价格]`（半开区间）：{_compact(inst["tariff"])}。
车辆表每行 `[id, 到达, 电量, priority]`：{_compact(inst["cars"])}。
约束：
- 车辆在桩上充电时长为 `ceil(电量/功率)` 分钟，开始后不可中断、不可换桩；同一桩同一时刻最多一辆车。
- 桩不得闲置：任一时刻若有空闲桩且有已到达未开始的车辆，该时刻必须开始充电。
- 被开始充电的车辆必须是当时已到达未开始车辆中 priority 数值最大者；同 priority 到达早者优先，再按 id。同一时刻有多个空闲桩时，编号小的桩先接车。
- 费用 = 充电各分钟所在时段价格之和，与功率无关。
输出 JSON 对象，只含以下字段：
- `schedule`：数组，每项 `[id, 桩, 开始, 结束, 费用]`，按开始、桩编号升序。
- `peak_cost`：整数，所有车辆落在 [{a},{b}) 内各分钟的费用之和。
- `finish_order`：数组，车辆 id 按结束时刻升序，同刻按 id。"""


# ---------------------------------------------------------------------------
# NX-15 隔离床位 + 感染清洁
# ---------------------------------------------------------------------------

def _gen_nx15(rng):
    beds = ["B1", "B2", "B3", "B4", "B5"]
    isolation = ["B1", "B2"]
    patients = {}
    for pid in _ids("P", 22):
        kind = "emergency" if rng.random() < 0.35 else "normal"
        patients[pid] = {
            "arrive": rng.randint(0, 80),
            "kind": kind,
            "infectious": rng.random() < 0.35,
            "service": rng.randint(10, 20) if kind == "emergency" else rng.randint(6, 15),
        }
    return {"beds": beds, "isolation": isolation, "clean": 7, "close": 90, "patients": patients}


def _solve_nx15(inst):
    iso = set(inst["isolation"])
    p = inst["patients"]
    served, pending, last_clean = _dispatch(inst["beds"], p, inst["clean"], inst["close"],
                                           eligible=lambda bed, pt: (not pt["infectious"]) or bed in iso)
    ew = sum(row[2] - p[row[0]]["arrive"] for row in served if p[row[0]]["kind"] == "emergency")
    return {
        "beds": served,
        "waiting": sorted(pending, key=lambda pid: (p[pid]["arrive"], pid)),
        "disinfect_until": dict(sorted(last_clean.items())),
        "emergency_wait": ew,
    }


def _accept_nx15(inst, ans):
    p = inst["patients"]
    inf_wait = [pid for pid in ans["waiting"] if p[pid]["infectious"]]
    jumped = any(row[2] > p[row[0]]["arrive"] and p[row[0]]["infectious"] for row in ans["beds"])
    return 2 <= len(ans["waiting"]) <= 6 and inf_wait and jumped and ans["emergency_wait"] > 0


def _prompt_nx15(inst):
    rows = [[pid, v["arrive"], v["kind"][0].upper(), int(v["infectious"]), v["service"]] for pid, v in sorted(inst["patients"].items())]
    return f"""
病床 {", ".join(inst["beds"])}，其中隔离床为 {", ".join(inst["isolation"])}，0 分钟全部空闲。患者表每行 `[id, 到达分钟, 类型(E=急诊/N=普通), 是否感染(1/0), 占床分钟]`：
{_compact(rows)}
约束：
- 一张床同一时刻最多一名患者，占床连续到结束；感染患者只能使用隔离床，非感染患者可用任何床；感染患者离床后该床清洁 {inst["clean"]} 分钟，清洁结束前不可用。
- 只有已到达的患者可以上床；上床时刻必须严格小于停止收治时刻 {inst["close"]}。
- 床位不得闲置：任一时刻若某床可用且存在已到达、未上床且可用该床的患者（且未停止收治），该时刻必须安排。
- 优先级：急诊高于普通；同类型到达早者优先；再按 id。同一时刻有多张床可用时按床号从小到大依次安排，每张床取当时可用该床的最高优先级患者。
输出 JSON 对象，只含以下字段：
- `beds`：数组，每项 `[id, 床, 上床分钟, 离床分钟]`，按上床分钟、床号升序。
- `waiting`：数组，到停止收治仍未上床的患者 id，按到达分钟、id 升序。
- `disinfect_until`：对象，只含接收过感染患者的床，值为该床最后一次清洁结束的分钟。
- `emergency_wait`：整数，已上床的急诊患者（上床分钟 − 到达分钟）之和。"""


# ---------------------------------------------------------------------------
# NX-16 多日采购（动态规划，统计最优解个数验证唯一）
# ---------------------------------------------------------------------------

def _gen_nx16(rng):
    n = 10
    kinds = ["normal"] * n
    for i in rng.sample(range(1, n), 3):
        kinds[i] = "hot"
    days = []
    for k in kinds:
        demand = rng.randint(5, 9) if k == "hot" else rng.randint(2, 7)
        days.append({"kind": k, "demand": demand, "price": rng.randint(8, 14), "cost": rng.randint(4, 9)})
    return {"capacity": 12, "box": 4, "days": days}


def _day(stock_old, buy, d):
    sell_old = min(stock_old, d["demand"])
    sell_new = min(buy, d["demand"] - sell_old)
    left_old = stock_old - sell_old
    left_new = buy - sell_new
    return sell_old + sell_new, left_old, left_new


def _solve_nx16(inst):
    days, cap = inst["days"], inst["capacity"]
    n = len(days)
    memo: dict[tuple[int, int], tuple[int, int, list]] = {}

    def best(i, carry):
        if i == n:
            return 0, 1, []
        key = (i, carry)
        if key in memo:
            return memo[key]
        d = days[i]
        options = range(0, cap - carry + 1, inst["box"]) if d["kind"] == "normal" else [0]
        top, count, plan = None, 0, None
        for buy in options:
            sold, left_old, left_new = _day(carry, buy, d)
            waste = left_old
            nxt = left_new
            if d["kind"] == "hot" or i == n - 1:
                waste += left_new
                nxt = 0
            gain = sold * d["price"] - buy * d["cost"]
            sub, sub_count, sub_plan = best(i + 1, nxt)
            total = gain + sub
            if top is None or total > top:
                top, count, plan = total, sub_count, [(buy, sold, waste)] + sub_plan
            elif total == top:
                count += sub_count
        memo[key] = (top, count, plan)
        return memo[key]

    profit, count, plan = best(0, 0)
    return {"buy": [p[0] for p in plan], "sold": [p[1] for p in plan], "waste": [p[2] for p in plan], "profit": profit}, count


def _accept_nx16(inst, ans_x):
    ans, count = ans_x
    days = inst["days"]
    naive = [d["demand"] if d["kind"] == "normal" else 0 for d in days]
    hot_sold = sum(s for s, d in zip(ans["sold"], days) if d["kind"] == "hot")
    return count == 1 and hot_sold > 0 and ans["buy"] != naive and sum(ans["waste"]) >= 2


def _prompt_nx16(inst):
    rows = [[i + 1, d["kind"], d["demand"], d["price"], d["cost"]] for i, d in enumerate(inst["days"])]
    return f"""
水果店连续经营 {len(inst["days"])} 天，库容 {inst["capacity"]}。每天表每行 `[第几天, 天气(normal/hot), 需求, 售价, 进价]`：{_compact(rows)}。
规则：
- 每天开门前可进货，进货量必须是 {inst["box"]} 的整数倍（可以为 0）；hot 天不能进货。进货后当天库存（前一天留下的 + 当天进货）不得超过库容。
- 当天销量 = min(需求, 当天库存)，不能惜售；先卖前一天留下的货，再卖当天进的货。
- 货物只能在进货当天和次日销售：次日结束仍未售出的旧货当天报废。hot 天结束时剩余库存全部报废。最后一天结束时剩余库存全部报废。
- 利润 = 各天（销量×售价 − 进货量×进价）之和。目标：利润最大（本实例最优进货方案唯一）。
输出 JSON 对象，只含以下字段：
- `buy`：长度 {len(inst["days"])} 的整数数组，每天进货量。
- `sold`：长度 {len(inst["days"])} 的整数数组，每天销量。
- `waste`：长度 {len(inst["days"])} 的整数数组，每天结束时报废量。
- `profit`：整数，最大利润。"""


# ---------------------------------------------------------------------------
# NX-17 有向换乘网络（预算 + 分时封路，穷举简单路径）
# ---------------------------------------------------------------------------

def _gen_nx17(rng):
    nodes = list("ABCDEFGHI")
    edges = []
    seen = set()
    for i, u in enumerate(nodes[:-1]):
        for v in rng.sample(nodes[i + 1:], min(len(nodes) - i - 1, rng.randint(1, 3))):
            seen.add((u, v))
    for _ in range(5):
        u, v = rng.sample(nodes[1:-1], 2)
        if (u, v) not in seen and (v, u) not in seen:
            seen.add((u, v))
    for u, v in sorted(seen):
        edges.append([u, v, rng.randint(2, 12), rng.randint(1, 6)])
    closures = []
    for e in rng.sample(edges, 4):
        a = rng.randint(0, 20)
        closures.append([e[0], e[1], a, a + rng.randint(4, 15)])
    return {"nodes": nodes, "edges": edges, "closures": closures, "budget": rng.randint(11, 16), "src": "A", "dst": "I"}


def _paths_nx17(inst):
    out = {}
    for u, v, m, c in inst["edges"]:
        out.setdefault(u, []).append((v, m, c))
    closed = {}
    for u, v, a, b in inst["closures"]:
        closed.setdefault((u, v), []).append((a, b))
    found, blocked = [], 0

    def walk(node, path, t, fee):
        nonlocal blocked
        if node == inst["dst"]:
            found.append((t, fee, path))
            return
        for v, m, c in sorted(out.get(node, [])):
            if v in path:
                continue
            if any(a <= t < b for a, b in closed.get((node, v), [])):
                blocked += 1
                continue
            if fee + c > inst["budget"]:
                continue
            walk(v, path + [v], t + m, fee + c)

    walk(inst["src"], [inst["src"]], 0, 0)
    found.sort()
    return found, blocked


def _solve_nx17(inst):
    found, blocked = _paths_nx17(inst)
    if not found:
        return {"path": [], "arrive": None, "cost": None, "alternatives": [], "reason": "no_budget_path"}, (found, blocked)
    t, fee, path = found[0]
    alts = [[p, a, c] for a, c, p in found[1:4]]
    return {"path": path, "arrive": t, "cost": fee, "alternatives": alts, "reason": ""}, (found, blocked)


def _accept_nx17(inst, ans_x):
    ans, (found, blocked) = ans_x
    if len(found) < 6 or blocked < 2:
        return False
    strict = found[0][:2] < found[1][:2]
    # 不考虑封路与预算时的最快路径必须不同于答案，防止“最短路即答案”
    fastest = _unconstrained_fastest(inst)
    return strict and fastest != ans["path"] and len({tuple(a[0]) for a in ans["alternatives"]}) == 3


def _unconstrained_fastest(inst):
    out = {}
    for u, v, m, _c in inst["edges"]:
        out.setdefault(u, []).append((v, m))
    best = None

    def walk(node, path, t):
        nonlocal best
        if node == inst["dst"]:
            if best is None or (t, path) < best:
                best = (t, path)
            return
        for v, m in out.get(node, []):
            if v not in path:
                walk(v, path + [v], t + m)

    walk(inst["src"], [inst["src"]], 0)
    return best[1] if best else None


def _prompt_nx17(inst):
    return f"""
有向线路网，站点 {"、".join(inst["nodes"])}。线路表每行 `[起点, 终点, 分钟, 费用]`，只能按起点→终点方向乘坐：{_compact(inst["edges"])}。
封闭表每行 `[起点, 终点, 开始, 结束]`：该线路在半开区间 [开始, 结束) 内封闭。
{_compact(inst["closures"])}
从 {inst["src"]} 于 0 分钟出发前往 {inst["dst"]}，预算 {inst["budget"]}。
约束：
- 不能在站点停留等待：到达某站即可立即进入下一段，进入时刻 = 到达该站时刻。
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

SPECS: dict[str, dict[str, Any]] = {
    "NX-09": {"title": "门诊多诊室与感染清场", "gen": _gen_nx09, "solve": _solve_nx09, "accept": _accept_nx09, "prompt": _prompt_nx09, "unwrap": False},
    "NX-10": {"title": "充电峰谷和预约占用", "gen": _gen_nx10, "solve": _solve_nx10, "accept": _accept_nx10, "prompt": _prompt_nx10, "unwrap": True},
    "NX-11": {"title": "冷链批次与装车窗口", "gen": _gen_nx11, "solve": _solve_nx11, "accept": _accept_nx11, "prompt": _prompt_nx11, "unwrap": True},
    "NX-12": {"title": "电梯停运下的外卖路线", "gen": _gen_nx12, "solve": _solve_nx12, "accept": _accept_nx12, "prompt": _prompt_nx12, "unwrap": True},
    "NX-13": {"title": "航班延误与机组时限", "gen": _gen_nx13, "solve": _solve_nx13, "accept": _accept_nx13, "prompt": _prompt_nx13, "unwrap": True},
    "NX-14": {"title": "充电站峰值排队", "gen": _gen_nx14, "solve": _solve_nx14, "accept": _accept_nx14, "prompt": _prompt_nx14, "unwrap": False},
    "NX-15": {"title": "隔离病床与清洁", "gen": _gen_nx15, "solve": _solve_nx15, "accept": _accept_nx15, "prompt": _prompt_nx15, "unwrap": False},
    "NX-16": {"title": "水果采购与热天损耗", "gen": _gen_nx16, "solve": _solve_nx16, "accept": _accept_nx16, "prompt": _prompt_nx16, "unwrap": True},
    "NX-17": {"title": "换乘预算和分时封路", "gen": _gen_nx17, "solve": _solve_nx17, "accept": _accept_nx17, "prompt": _prompt_nx17, "unwrap": True},
    "NX-18": {"title": "冷藏配送和电梯停运", "gen": _gen_nx18, "solve": _solve_nx18, "accept": _accept_nx18, "prompt": _prompt_nx18, "unwrap": True},
}


def solve(item_id: str, instance: dict) -> dict:
    spec = SPECS[item_id]
    out = spec["solve"](instance)
    return out[0] if spec["unwrap"] else out


def build_item(item_id: str) -> dict[str, Any]:
    spec = SPECS[item_id]
    offset = int(item_id.split("-")[1]) * 100000
    for k in range(MAX_TRIES):
        seed = BASE_SEED + offset + k
        inst = spec["gen"](random.Random(seed))
        inst = json.loads(json.dumps(inst))  # 规范成纯 JSON
        raw = spec["solve"](inst)
        if spec["accept"](inst, raw):
            answer = raw[0] if spec["unwrap"] else raw
            return {"item_id": item_id, "title": spec["title"], "seed": seed, "instance": inst,
                    "prompt": spec["prompt"](inst).strip(), "answer": json.loads(json.dumps(answer))}
    raise RuntimeError(f"{item_id}: no acceptable instance in {MAX_TRIES} seeds")


def build_all() -> dict[str, Any]:
    return {"version": "20261012", "base_seed": BASE_SEED, "items": [build_item(i) for i in SPECS]}
