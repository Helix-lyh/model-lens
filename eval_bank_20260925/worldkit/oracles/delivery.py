"""配送题族的独立复核器（暴力枚举，按渲染后的题面逐句实现）。

约束：不得 import worldkit 的引擎、题族或答案模块（tests/test_worldkit_delivery.py 用 AST 检查）。
只吃世界字典；模块键缺失即该规则不存在。不剪枝，枚举所有合法路线。
"""
from __future__ import annotations

NO_SOLUTION = "无解"


def _minutes(roads, x, y):
    if x == y:
        return 0
    key = x + "-" + y
    return roads[key] if key in roads else roads[y + "-" + x]


def _resolve_shocks(mods, force=None):
    """题面：洪涝封楼与楼宇封闭至多生效一条——开始时刻较早者生效；同时刻洪涝优先。"""
    if "mutex" not in mods:
        return dict(mods), None
    cands = []
    if "flood" in mods:
        cands.append((mods["flood"]["t"], 0, "flood", None, None))
    if "closed" in mods:
        for bld in sorted(mods["closed"]["spans"]):
            for span in mods["closed"]["spans"][bld]:
                cands.append((span[0], 1, "closed", bld, span))
    if len(cands) < 2:
        return dict(mods), None
    if force:
        cands = [c for c in cands if c[2] == force]
    if not cands:
        return dict(mods), None
    cands.sort(key=lambda c: (c[0], c[1], c[3] or ""))
    _t, _p, kind, bld, span = cands[0]
    out = dict(mods)
    if kind == "flood":
        out.pop("closed", None)
    else:
        out.pop("flood", None)
        out["closed"] = {"spans": {bld: [span]}}
    return out, kind


def _routes(orders, free_return):
    """显式栈深搜：每次选一个未送订单；允许随时回站时，两单之间可插一次 W。"""
    stack = [((), frozenset(orders))]
    while stack:
        route, left = stack.pop()
        if not left:
            yield route
            continue
        for oid in sorted(left):
            stack.append((route + (oid,), left - {oid}))
            if free_return and route and route[-1] != "W":
                stack.append((route + ("W", oid), left - {oid}))


def _run(world, mods, route):
    """返回 (total, late_n, walk) 或 None（不可行）。"""
    roads = world["data"]["roads"]
    orders = world["data"]["orders"]
    use_ready = "ready" in mods
    t = 0
    here = "W"
    floor_now = 0
    in_a_row = 0
    seen = set()
    walk = 0
    done = []

    def descend_and_drive(target):
        nonlocal t
        if floor_now and "down" in mods:
            t += floor_now * mods["down"]["rate"]
        leg = _minutes(roads, here, target)
        if "congestion" in mods and t >= mods["congestion"]["from"]:
            leg = leg * mods["congestion"]["mult"]
        t += leg

    for stop in route:
        if stop == "W":
            if here != "W":
                descend_and_drive("W")
                here, floor_now, in_a_row = "W", 0, 0
            continue
        if "carry" in mods and in_a_row >= mods["carry"]["max"] and here != "W":
            descend_and_drive("W")
            here, floor_now, in_a_row = "W", 0, 0
        o = orders[stop]
        bld = o["building"]
        descend_and_drive(bld)
        arrive_ground = t
        fl = mods.get("flood")
        if fl and fl["building"] == bld and t >= fl["t"]:
            return None
        if "register" in mods and bld not in seen:
            t += mods["register"]["minutes"].get(bld, 0)
        seen.add(bld)
        if "closed" in mods:
            spans = sorted(mods["closed"]["spans"].get(bld, []))
            waiting = True
            while waiting:
                waiting = False
                for a, z in spans:
                    if a <= t < z:
                        t = z
                        waiting = True
        if use_ready and t < o.get("ready", 0):
            t = o["ready"]
        if "outage" in mods:
            judge_at = t if mods["outage"].get("check_at", "climb_start") == "climb_start" else arrive_ground
            stopped = False
            for a, z in mods["outage"]["spans"].get(bld, []):
                if a <= judge_at < z:
                    stopped = True
            if stopped:
                t += 2 * o["floor"]
                walk += 2 * o["floor"]
            else:
                t += o["floor"]
        else:
            t += o["floor"]
        if fl and fl["building"] == bld and fl.get("scope", "deliver") == "deliver" and t >= fl["t"]:
            return None
        done.append((stop, t))
        here, floor_now, in_a_row = bld, o["floor"], in_a_row + 1
    late = 0
    for oid, when in done:
        o = orders[oid]
        bad = when > o["deadline"]
        if "cold" in mods:
            start = o.get("ready", 0) if use_ready else 0
            bad = bad or when > start + mods["cold"]["limit"]
        late += bad
    return {"total": done[-1][1], "late_n": late, "walk": walk}


def solve(world, force=None):
    """返回 (status, 最优方案主值集合, 最优目标下任一方案的指标)。"""
    mods, active = _resolve_shocks(world["modules"], force)
    cancelled = set(mods.get("cancel", {}).get("ids", []))
    todo = [o for o in world["data"]["orders"] if o not in cancelled]
    results = []
    for route in _routes(todo, "return_w" in mods):
        m = _run(world, mods, route)
        if m is not None:
            results.append(m)
    if not results:
        return "infeasible", None, active
    rank = lambda m: tuple(m[k] for k in world["objective"])
    best = min(rank(m) for m in results)
    tops = [m for m in results if rank(m) == best]
    return "ok", tops, active


def answers(world):
    """按问题取值，供与引擎对拍；同时返回主值在全部最优方案上的取值集合。"""
    status, tops, active = solve(world)
    mains = [q for q in world["questions"] if not q.get("cf")]
    if status != "ok":
        main_set = frozenset({(NO_SOLUTION,)})
    else:
        main_set = frozenset(tuple(m[q["metric"]] for q in mains) for m in tops)
    out = {}
    for q in world["questions"]:
        if q.get("cf"):
            other = "closed" if active == "flood" else "flood"
            st, cf_tops, _ = solve(world, force=other)
            vals = {m[q["metric"]] for m in cf_tops} if st == "ok" else {NO_SOLUTION}
        else:
            vals = {m[q["metric"]] for m in tops} if status == "ok" else {NO_SOLUTION}
        out[q["name"]] = vals
    return main_set, out
