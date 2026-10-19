"""配送题族：单骑手、多楼宇、顺序自选。

每个模块的题面条款与语义判定写在同一节里；到达楼下后的处理顺序由 ARRIVAL_PHASES 统一给出，
simulate 与题面都按它展开，二者不会各写一份。
"""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
from typing import Iterator

from eval_bank_20260925.worldkit.core import Counterfactual, Module, Outcome


def _c(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _road(roads: dict, a: str, b: str) -> int:
    if a == b:
        return 0
    return roads[f"{a}-{b}"] if f"{a}-{b}" in roads else roads[f"{b}-{a}"]


def _ready_on(world: dict) -> bool:
    return "ready" in world["modules"]


# ---------------------------------------------------------------------------
# 模块：题面条款（text）。语义在 simulate 中按同名模块分支实现，分支旁注明模块 id。
# ---------------------------------------------------------------------------

def _t_outage(p, w):
    when = "开始上楼的时刻" if p.get("check_at", "climb_start") == "climb_start" else "到达楼宇地面的时刻"
    return (f"电梯停运区间（半开区间 [开始, 结束)）：{_c(p['spans'])}。若{when}处于该楼宇停运区间内，本次上楼步行，每层 2 分钟；"
            "否则乘电梯，每层 1 分钟。上楼期间电梯状态变化不影响本次上楼。")


def _t_register(p, w):
    return f"首次进入楼宇需在地面登记（分钟；登记在楼外进行，不受封闭影响；同一楼宇再次进入不再登记）：{_c(p['minutes'])}。"


def _t_closed(p, w):
    return f"楼宇封闭区间（半开）：{_c(p['spans'])}。处于封闭时须在楼外等到封闭结束。"


def _t_ready(p, w):
    return "订单在出餐时刻 ready 之前不能开始上楼，早到须在地面等到 ready。"


def _t_down(p, w):
    return f"送达后回到地面每层 {p['rate']} 分钟（不受电梯状态影响），再出发去下一单。"


def _t_congestion(p, w):
    return f"从时刻 {p['from']} 起出发的整段道路时间×{p['mult']}（按下楼回到地面后离开的时刻判断）。"


def _t_carry(p, w):
    s = f"连续配送上限 {p['max']} 单：已连续送满 {p['max']} 单且仍有未送订单时，须先回 W 再继续"
    if "return_w" not in w["modules"]:
        s += "；未送满不得提前回 W"
    return s + "。"


def _t_return_w(p, w):
    s = "未送满也可以在两单之间随时先回 W 再继续（往返按道路分钟计）"
    if "carry" in w["modules"]:
        s += "；回 W 后连续配送计数重新从 0 开始"
    return s + "。"


def _t_cancel(p, w):
    return f"取消订单（不必配送）：{_c(p['ids'])}。"


def _t_flood(p, w):
    if p.get("scope", "deliver") == "deliver":
        need = "该楼的订单必须在此时刻之前送达，否则方案不可行"
    else:
        need = "必须在此时刻之前到达该楼地面，否则方案不可行"
    return f"从时刻 {p['t']} 起楼宇 {p['building']} 因洪涝不可进入：{need}。"


def _t_cold(p, w):
    base = "ready + " if _ready_on(w) else "0 分钟起 "
    return f"冷链时限：送达时刻超过 {base}{p['limit']} 亦计迟到。"


def _t_mutex(p, w):
    return ("突发：洪涝封楼与上面的楼宇封闭至多生效一条——开始时刻较早者生效；同时刻洪涝优先。未生效者视为不存在。")


def _ablate_mutex(world: dict) -> dict:
    x = copy.deepcopy(world)
    x["modules"].pop("mutex", None)
    return x


MODULES = {m.id: m for m in [
    Module("outage", "电梯停运", 10, _t_outage),
    Module("register", "首次登记", 20, _t_register),
    Module("closed", "楼宇封闭", 25, _t_closed),
    Module("ready", "出餐时刻", 27, _t_ready),
    Module("down", "下楼耗时", 30, _t_down),
    Module("congestion", "道路拥堵", 35, _t_congestion),
    Module("carry", "连续配送上限", 40, _t_carry),
    Module("return_w", "随时回站", 41, _t_return_w, kind="constraint", relaxing=False),
    Module("cancel", "订单取消", 50, _t_cancel, kind="constraint", relaxing=False),
    Module("flood", "洪涝封楼", 55, _t_flood, kind="constraint"),
    Module("cold", "冷链时限", 60, _t_cold),
    Module("mutex", "洪涝封闭互斥", 70, _t_mutex, kind="constraint", ablate=_ablate_mutex,
           relaxing=False),
]}

# 到达楼宇地面后的处理阶段（顺序即语义顺序）。
ARRIVAL_PHASES = [
    ("register", "完成需要的登记"),
    ("closed", "若处于封闭则等到结束"),
    ("ready", "若早于该订单 ready 则等到 ready"),
]

METRICS = {
    "total": "最后一单送达时刻",
    "late_n": "迟到订单数",
    "walk": "全程步行上楼分钟数之和（乘电梯与下楼不计）",
}

OBJECTIVE_PHRASES = {
    "late_n": "迟到订单数最少",
    "total": "最后一单送达时刻最小",
    "walk": "全程步行上楼分钟数之和（乘电梯与下楼不计）最小",
}

PRIO = ("flood", "closed")


# ---------------------------------------------------------------------------
# 互斥突发与反事实
# ---------------------------------------------------------------------------

def _shock_events(world: dict) -> list[dict]:
    m = world["modules"]
    ev = []
    if "flood" in m:
        ev.append({"t": m["flood"]["t"], "kind": "flood"})
    for b, spans in (m.get("closed") or {}).get("spans", {}).items():
        for a, z in spans:
            ev.append({"t": a, "kind": "closed", "building": b, "span": [a, z]})
    return ev


def _effective(world: dict) -> dict:
    """mutex 生效时只保留开始最早的一条突发（同刻洪涝优先）；force 指定反事实中生效的类别。"""
    m = world["modules"]
    if "mutex" not in m:
        return world
    ev = _shock_events(world)
    if len(ev) < 2:
        return world
    force = m["mutex"].get("force")
    pool = [e for e in ev if e["kind"] == force] if force else ev
    if not pool:
        return world
    active = min(pool, key=lambda e: (e["t"], PRIO.index(e["kind"]), e.get("building") or ""))
    x = copy.deepcopy(world)
    if active["kind"] == "flood":
        x["modules"].pop("closed", None)
    else:
        x["modules"].pop("flood", None)
        x["modules"]["closed"] = {"spans": {active["building"]: [active["span"]]}}
    x["active_shock"] = active["kind"]
    return x


def _swap_shock(world: dict) -> dict:
    """互斥规则被消融时两条突发同时生效，「另一条」无从谈起，反事实世界即原世界。"""
    if "mutex" not in world["modules"]:
        return world
    live = _effective(world)
    other = [k for k in PRIO if k != live.get("active_shock")][0]
    x = copy.deepcopy(world)
    x["modules"]["mutex"] = dict(x["modules"]["mutex"], force=other)
    return x


COUNTERFACTUALS = {
    "swap_shock": Counterfactual(
        _swap_shock, lambda w: "若改为另一条突发生效（本应生效的那条视为不存在，另一条照常发生），"),
}


def _flip(mid: str, key: str, a: str, b: str, default: str):
    def fn(world: dict) -> dict | None:
        if mid not in world["modules"]:
            return None
        x = copy.deepcopy(world)
        cur = x["modules"][mid].get(key, default)
        x["modules"][mid][key] = b if cur == a else a
        return x
    return fn


# 已登记的歧义点：题面不变，只换语义读法，测主值是否敏感。
READINGS = {
    "洪涝：送达前 / 到达前": _flip("flood", "scope", "deliver", "enter", "deliver"),
    "停运判定：开始上楼时 / 到达地面时": _flip("outage", "check_at", "climb_start", "arrival", "climb_start"),
}


# ---------------------------------------------------------------------------
# 题族
# ---------------------------------------------------------------------------

class DeliveryFamily:
    id = "delivery"
    modules = MODULES
    metrics = METRICS
    counterfactuals = COUNTERFACTUALS
    readings = READINGS

    def effective(self, world: dict) -> dict:
        return _effective(world)

    def active_orders(self, world: dict) -> list[str]:
        cancelled = set((world["modules"].get("cancel") or {}).get("ids", []))
        return sorted(o for o in world["data"]["orders"] if o not in cancelled)

    def plans(self, world: dict) -> Iterator[tuple]:
        active = self.active_orders(world)
        free_return = "return_w" in world["modules"]
        for perm in itertools.permutations(active):
            if not free_return:
                yield perm
                continue
            for mask in range(2 ** max(0, len(perm) - 1)):
                route = [perm[0]]
                for k, oid in enumerate(perm[1:]):
                    if mask >> k & 1:
                        route.append("W")
                    route.append(oid)
                yield tuple(route)

    def simulate(self, world: dict, plan: tuple) -> Outcome | None:
        m = world["modules"]
        roads, orders = world["data"]["roads"], world["data"]["orders"]
        pos, clock, prev_floor, carry = "W", 0, 0, 0
        visited: set[str] = set()
        arrivals: list[list] = []
        walk, boundary = 0, 0
        fired: set[str] = set()

        def leave_and_travel(dest: str) -> None:
            nonlocal clock
            if "down" in m and prev_floor:  # down
                clock += prev_floor * m["down"]["rate"]
                fired.add("down")
            d = _road(roads, pos, dest)
            if "congestion" in m and clock >= m["congestion"]["from"] and d:  # congestion
                d *= m["congestion"]["mult"]
                fired.add("congestion")
            clock += d

        for step in plan:
            if step == "W":  # return_w
                if pos != "W":
                    leave_and_travel("W")
                    pos, prev_floor, carry = "W", 0, 0
                    fired.add("return_w")
                continue
            if "carry" in m and carry >= m["carry"]["max"] and pos != "W":  # carry
                leave_and_travel("W")
                pos, prev_floor, carry = "W", 0, 0
                fired.add("carry")
            o = orders[step]
            b = o["building"]
            leave_and_travel(b)
            flood = m.get("flood")
            if flood and b == flood["building"] and clock >= flood["t"]:  # flood（到达即不可进入）
                return None
            ground = clock
            for mid, _phrase in ARRIVAL_PHASES:
                if mid not in m:
                    continue
                if mid == "register" and b not in visited:
                    cost = m["register"]["minutes"].get(b, 0)
                    clock += cost
                    if cost:
                        fired.add("register")
                elif mid == "closed":
                    spans = sorted(m["closed"]["spans"].get(b, []))
                    waiting = True
                    while waiting:
                        waiting = False
                        for a, z in spans:
                            if a <= clock < z:
                                boundary += clock == a
                                clock = z
                                fired.add("closed")
                                waiting = True
                elif mid == "ready":
                    r = o.get("ready", 0)
                    boundary += clock == r and r > 0
                    if clock < r:
                        clock = r
                        fired.add("ready")
            visited.add(b)
            up = o["floor"]
            if "outage" in m:  # outage
                at = clock if m["outage"].get("check_at", "climb_start") == "climb_start" else ground
                spans = m["outage"]["spans"].get(b, [])
                boundary += any(at in (a, z) for a, z in spans)
                if any(a <= at < z for a, z in spans):
                    walk += up * 2
                    up *= 2
                    fired.add("outage")
            clock += up
            if flood and b == flood["building"] and flood.get("scope", "deliver") == "deliver" and clock >= flood["t"]:
                return None
            arrivals.append([step, clock])
            pos, prev_floor, carry = b, o["floor"], carry + 1
        late = []
        for oid, t in arrivals:
            o = orders[oid]
            r = o.get("ready", 0) if _ready_on(world) else 0
            cold_late = "cold" in m and t > r + m["cold"]["limit"]  # cold
            if cold_late and t <= o["deadline"]:
                fired.add("cold")
            if t > o["deadline"] or cold_late:
                late.append(oid)
        if "flood" in m and any(orders[oid]["building"] == m["flood"]["building"] for oid, _ in arrivals):
            fired.add("flood")
        if "cancel" in m:
            fired.add("cancel")
        return Outcome(plan, {"total": arrivals[-1][1], "late_n": len(late), "walk": walk},
                       [arrivals, sorted(late)], frozenset(fired), boundary)

    # -- 题面 ------------------------------------------------------------------

    def header(self, world: dict) -> str:
        d = world["data"]
        rows = [[a, b, v] for a, b, v in ((*k.split("-"), v) for k, v in d["roads"].items())]
        ready = _ready_on(world)
        cols = "[id, 楼宇, 楼层, ready, deadline]" if ready else "[id, 楼宇, 楼层, deadline]"
        orders = [[oid, o["building"], o["floor"], *([o.get("ready", 0)] if ready else []), o["deadline"]]
                  for oid, o in sorted(d["orders"].items())]
        avail = "" if ready else "，订单均在 0 分钟可配送"
        phases = [p for mid, p in ARRIVAL_PHASES if mid in world["modules"]]
        flow = "，然后".join(phases + ["上楼"])
        down = "" if "down" in world["modules"] else "送达后回到地面不耗时。"
        lift = "" if "outage" in world["modules"] else "上楼乘电梯，每层 1 分钟。"
        return "\n".join([
            f"{world['data'].get('role', '骑手')} 0 分钟在站点 W（地面），完成全部订单，顺序自选。任意两地点之间道路双向可走，"
            f"行驶分钟表每行 `[地点, 地点, 分钟]`：{_c(rows)}。"
            "表中一行就是这两点之间一次直达的行驶分钟，不经其他地点。",
            f"订单表每行 `{cols}`{avail}：{_c(orders)}。",
            f"到达楼宇地面后：{flow}。{lift}送达时刻 = 到达所在楼层的时刻。{down}"
            "下一单在同一楼宇时道路分钟为 0，仍需下楼再上楼。最后一单送达即结束，不再下楼。",
            "除规则明确要求的等待外，不得在任何地点主动停留。送达时刻 > deadline 为迟到；deadline 不限制可行性。",
        ])

    def objective_text(self, world: dict) -> str:
        layers = [OBJECTIVE_PHRASES[m] for m in world["objective"]]
        if len(layers) == 1:
            return f"目标：使{layers[0]}。"
        s = f"目标：先使{layers[0]}"
        for p in layers[1:-1]:
            s += f"，在此前提下使{p}"
        return s + f"；若仍有多个顺序并列，取{layers[-1]}者。"


FAMILY = DeliveryFamily()


# ---------------------------------------------------------------------------
# 采样：按场景配置的参数范围与难度向量生成世界
# ---------------------------------------------------------------------------

def _rng_span(rng, lo_hi_start, lo_hi_len):
    a = rng.randint(*lo_hi_start)
    return [a, a + rng.randint(*lo_hi_len)]


def questions_for(tier: dict) -> list[dict]:
    if "late_n" not in tier["objective"]:
        return [{"name": "plan", "type": "plan", "metric": "total", "points": 10},
                {"name": "total", "metric": "total", "points": 10}]
    third = "late_n"
    if tier.get("cf"):
        return [{"name": "plan", "type": "plan", "metric": "total", "points": 6},
                {"name": "total", "metric": "total", "points": 5},
                {"name": third, "metric": third, "points": 4},
                {"name": "cf_total", "metric": "total", "points": 5, "cf": "swap_shock"}]
    return [{"name": "plan", "type": "plan", "metric": "total", "points": 8},
            {"name": "total", "metric": "total", "points": 6},
            {"name": third, "metric": third, "points": 6}]


def sample(rng, cfg: dict, tier: dict) -> dict:
    p = cfg["params"]
    blds = [f"L{i}" for i in range(1, tier["buildings"] + 1)]
    names = ["W"] + blds
    pts = {n: (rng.randint(0, p["grid"]), rng.randint(0, p["grid"])) for n in names}
    roads = {f"{a}-{b}": max(p["road_min"], abs(pts[a][0] - pts[b][0]) + abs(pts[a][1] - pts[b][1]) + rng.randint(0, 2))
             for a, b in itertools.combinations(names, 2)}
    mods_on = set(tier["modules"])
    n = tier["orders"] + (1 if "cancel" in mods_on else 0)
    horizon = tier["orders"] * p["minutes_per_order"]
    ids = [chr(ord("A") + i) for i in range(n)]
    orders = {}
    for oid in ids:
        o = {"building": rng.choice(blds), "floor": rng.randint(*p["floor"]),
             "deadline": rng.randint(int(horizon * p["deadline_frac"][0]), int(horizon * p["deadline_frac"][1]))}
        if "ready" in mods_on:
            o["ready"] = rng.randint(0, int(horizon * p["ready_frac"])) if rng.random() < 0.6 else 0
        orders[oid] = o
    mods: dict = {}
    if "outage" in mods_on:
        mods["outage"] = {"spans": {b: [_rng_span(rng, (0, int(horizon * 0.6)), p["outage_len"])] for b in blds}}
    if "register" in mods_on:
        mods["register"] = {"minutes": {b: rng.randint(*p["register"]) for b in blds}}
    if "closed" in mods_on:
        mods["closed"] = {"spans": {rng.choice(blds): [_rng_span(rng, (5, int(horizon * 0.6)), p["closed_len"])]}}
    if "ready" in mods_on:
        mods["ready"] = {}
    if "down" in mods_on:
        mods["down"] = {"rate": 1}
    if "congestion" in mods_on:
        mods["congestion"] = {"from": rng.randint(int(horizon * 0.2), int(horizon * 0.6)), "mult": p["congestion_mult"]}
    if "carry" in mods_on:
        lo, hi = tier.get("carry", [2, max(2, tier["orders"] - 1)])
        mods["carry"] = {"max": rng.randint(lo, hi)}
    if "return_w" in mods_on:
        mods["return_w"] = {}
    if "cancel" in mods_on:
        mods["cancel"] = {"ids": [ids[-1]]}
    if "flood" in mods_on:
        mods["flood"] = {"t": rng.randint(int(horizon * 0.25), int(horizon * 0.8)), "building": rng.choice(blds),
                         "scope": "deliver"}
    if "cold" in mods_on:
        mods["cold"] = {"limit": rng.randint(*p["cold_limit"])}
    if "mutex" in mods_on:
        mods["mutex"] = {}
    world = {
        "family": "delivery",
        "data": {"roads": roads, "orders": orders, "role": "冷藏骑手" if "cold" in mods else "骑手"},
        "modules": mods,
        "objective": list(tier["objective"]),
        "objective_conditions": {k: v for k, v in tier.get("objective_conditions", {}).items() if k in tier["objective"]},
        "questions": questions_for(tier),
        "background": list(tier.get("background", [])),
        "gates": dict(tier.get("gates", {})),
    }
    _anchor(rng, world, bool(tier.get("infeasible")))
    return world


def _relaxed_best(world: dict, drop: tuple[str, ...]) -> tuple[dict[str, int], dict[str, int]] | None:
    """去掉指定模块后的最优送达时刻，以及每栋楼在全部可行方案里的最早送完时刻。"""
    from eval_bank_20260925.worldkit import accel
    probe = copy.deepcopy(world)
    for mid in drop:
        probe["modules"].pop(mid, None)
    info = accel.trajectory(probe, max_plans=400_000, seconds=60)
    if info.get("error") or info.get("status") != "ok":
        return None
    at = {k: int(v) for k, v in info["arrivals"].items()}
    earliest = {k: int(v) for k, v in info["min_finish"].items()}
    return at, earliest


def _anchor(rng, world: dict, infeasible: bool) -> None:
    """把时间参数锚定在松弛轨迹附近，使时限、出餐、封闭、停运、洪涝大概率卡在真实路线上。
    纯随机取值时这些规则多数不承重（试采样中洪涝 69/73 不承重）。"""
    m, orders = world["modules"], world["data"]["orders"]
    relaxed = _relaxed_best(world, ("outage", "closed", "flood", "mutex", "ready", "cold"))
    if relaxed is None:
        return
    at, _ = relaxed
    ground = {oid: t - orders[oid]["floor"] for oid, t in at.items()}
    first = {}
    for oid, g in ground.items():
        b = orders[oid]["building"]
        first[b] = min(first.get(b, g), g)
    for oid, t in at.items():
        o = orders[oid]
        if "ready" in m:
            o["ready"] = max(0, ground[oid] + rng.randint(-2, 6)) if rng.random() < 0.5 else 0
        o["deadline"] = max(5, t + rng.randint(-6, 6), o.get("ready", 0) + o["floor"] + 2)
    if "closed" in m:
        (b, spans), = m["closed"]["spans"].items()
        if b in first:
            a = max(1, first[b] - rng.randint(0, 3))
            m["closed"]["spans"] = {b: [[a, a + spans[0][1] - spans[0][0]]]}
    if "outage" in m:
        for b, spans in m["outage"]["spans"].items():
            if b in first and rng.random() < 0.6:
                a = max(0, first[b] - rng.randint(0, 4))
                m["outage"]["spans"][b] = [[a, a + spans[0][1] - spans[0][0]]]
    if "flood" in m:
        _anchor_flood(rng, world, infeasible)


def _anchor_flood(rng, world: dict, infeasible: bool) -> None:
    """洪涝时刻：可解档取在「最早能送完该楼」与「松弛最优送完该楼」之间，迫使最优路线改变；
    无解档取在「最早能送完该楼」之前。"""
    m, orders = world["modules"], world["data"]["orders"]
    drop = ("flood", "closed", "mutex") if "mutex" in m else ("flood",)
    relaxed = _relaxed_best(world, drop)
    if relaxed is None:
        return
    at, earliest = relaxed
    by_b: dict[str, list[str]] = {}
    for oid in at:
        by_b.setdefault(orders[oid]["building"], []).append(oid)
    cands = [b for b, ids in by_b.items() if len(ids) >= 2] or list(by_b)
    b = rng.choice(sorted(cands))
    lo = earliest[b]
    hi = max(t for oid, t in at.items() if orders[oid]["building"] == b)
    if infeasible:
        t = max(1, lo - rng.randint(0, 2))
    elif hi > lo:
        t = rng.randint(lo + 1, hi)
    else:
        t = hi + 1
    m["flood"].update(t=t, building=b)
    if "mutex" in m and "closed" in m:
        _settle_mutex(rng, world, flood_first=infeasible or rng.random() < 0.5)


def _settle_mutex(rng, world: dict, flood_first: bool) -> None:
    """互斥下只有先发生的突发生效，另一条删了也不改主值，只能由反事实题考察，故记为背景。"""
    m = world["modules"]
    t = m["flood"]["t"]
    (b, [[a, z]]), = m["closed"]["spans"].items()
    if flood_first and a < t:
        shift = t + rng.randint(0, 4) - a
    elif not flood_first and a >= t:
        shift = max(1, t - rng.randint(1, 3)) - a
    else:
        shift = 0
    m["closed"]["spans"] = {b: [[a + shift, z + shift]]}
    idle = "closed" if flood_first else "flood"
    if idle not in world["background"]:
        world["background"].append(idle)


def perturbations(world: dict) -> list[tuple[str, dict]]:
    """无解题的近邻：每个变体只改一个参数。"""
    out = []
    m = world["modules"]

    def variant(desc, fn):
        x = copy.deepcopy(world)
        fn(x["modules"])
        out.append((desc, x))

    if "flood" in m:
        for d in (2, 4, 6, 9, 12):
            variant(f"洪涝时刻推迟 {d} 分钟", lambda mm, d=d: mm["flood"].update(t=mm["flood"]["t"] + d))
    if "register" in m:
        for b, v in m["register"]["minutes"].items():
            if v:
                variant(f"{b} 登记减为 0", lambda mm, b=b: mm["register"]["minutes"].update({b: 0}))
    if "closed" in m:
        for b, spans in m["closed"]["spans"].items():
            variant(f"{b} 封闭缩短 5 分钟",
                    lambda mm, b=b: mm["closed"]["spans"].update({b: [[a, max(a + 1, z - 5)] for a, z in mm["closed"]["spans"][b]]}))
    if "outage" in m:
        for b in m["outage"]["spans"]:
            variant(f"{b} 电梯不停运", lambda mm, b=b: mm["outage"]["spans"].update({b: []}))
    if "congestion" in m:
        variant("拥堵推迟 5 分钟开始", lambda mm: mm["congestion"].update({"from": mm["congestion"]["from"] + 5}))
    return out


def extreme_world() -> dict:
    path = Path(__file__).resolve().parents[1] / "worlds" / "delivery" / "extreme.json"
    return json.loads(path.read_text(encoding="utf-8"))
