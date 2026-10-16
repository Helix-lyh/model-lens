"""20261019 推理题：分档、门禁记录、删除测试（独立模拟器）、唯一最优、Schema、约束完整性（非词表禁令）。

本文件中的 _sim_* 均为独立实现（逐分钟推进 / 显式穷举），不调用 reasoning_gen 的求解器，
只复用其中的“删除条件”数据变换（CONDITIONS 中的 mutator）。
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from eval_bank_20260925 import reasoning_gen as gen
from eval_bank_20260925.next_reasoning import FROZEN, ITEMS, parse_answer, reference_answer, reference_text, render_reasoning_prompt, score_reasoning

ROOT = Path(__file__).resolve().parents[1]
ROWS = {row["item_id"]: row for row in FROZEN["items"]}
INST = {k: v["instance"] for k, v in ROWS.items()}


def _price(tariff, m):
    return next(p for a, b, p in tariff if a <= m < b)


# ---------------- 独立模拟器 ----------------

def _sim_rooms(units, patients, clean, close, can, emergency_first, caps=None, light_clean=0, infect_deadline=None, outages=None, clean_after=None):
    busy_until = dict.fromkeys(units, 0)
    used = dict.fromkeys(units, 0)
    started, rows, last_clean = set(), [], {}
    for t in range(close):
        for u in units:
            if busy_until[u] > t:
                continue
            if any(a <= t < b for a, b in (outages or {}).get(u, [])):
                continue
            if caps and used[u] >= caps.get(u, 10**9):
                continue
            cand = []
            for pid, p in patients.items():
                if pid in started or p["arrive"] > t or not can(u, p):
                    continue
                if infect_deadline is not None and p["infectious"] and t >= infect_deadline:
                    continue
                cand.append((0 if (not emergency_first or p["kind"] == "emergency") else 1, p["arrive"], pid))
            if not cand:
                continue
            pid = min(cand)[2]
            p = patients[pid]
            started.add(pid)
            used[u] += 1
            rows.append([pid, u, t, t + p["service"]])
            cur_clean = clean
            if clean_after and p["infectious"] and t >= clean_after[0]:
                cur_clean = clean_after[1]
            extra = cur_clean if p["infectious"] else light_clean
            busy_until[u] = t + p["service"] + extra
            if p["infectious"]:
                last_clean[u] = t + p["service"] + cur_clean
    rows.sort(key=lambda r: (r[2], r[1]))
    waiting = sorted((pid for pid in patients if pid not in started), key=lambda x: (patients[x]["arrive"], x))
    return rows, waiting, last_clean


def _sim09(i):
    rows, waiting, _ = _sim_rooms(i["rooms"], i["patients"], i["clean"], i["close"],
                                  lambda u, p: not (p["infectious"] and u in i["no_infectious"]), i["emergency_first"],
                                  caps=i["room_cap"], infect_deadline=i["infect_cutoff"],
                                  outages=i.get("outages"), clean_after=i.get("clean_after"))
    return {"served": rows, "waiting": waiting, "last_end": max(r[3] for r in rows),
            "infectious_rooms": sorted({r[1] for r in rows if i["patients"][r[0]]["infectious"]})}


def _sim15(i):
    rows, waiting, lc = _sim_rooms(i["beds"], i["patients"], i["clean"], i["close"],
                                   lambda b, p: (not p["infectious"] or b in i["isolation"]) and (b not in i["emergency_only"] or p["kind"] == "emergency"),
                                   i["emergency_first"], caps=i["bed_cap"], light_clean=i["light_clean"],
                                   outages=i.get("outages"), clean_after=i.get("clean_after"))
    return {"beds": rows, "waiting": waiting, "disinfect_until": dict(sorted(lc.items())),
            "emergency_wait": sum(r[2] - i["patients"][r[0]]["arrive"] for r in rows if i["patients"][r[0]]["kind"] == "emergency")}


def _sim10(i):
    horizon = i["tariff"][-1][1] + 64
    used = {p: [False] * horizon for p in i["piles"]}
    load = [0] * horizon
    gap = i.get("gap", 0)
    max_c = i.get("max_concurrent", 10**9)
    for p, ws in i["reservations"].items():
        for a, b in ws:
            for m in range(a, min(b, horizon)):
                used[p][m] = True
    assign, rejected = [], []
    for vid, arr, energy, dl in i["vehicles"]:
        best = None
        for p in sorted(i["piles"]):
            if energy < i["min_energy"].get(p, 0):
                continue
            d = -(-energy // i["piles"][p])
            fails = i.get("pile_fail", {}).get(p, []) + i.get("blackout", [])
            for s in range(arr, dl - d + 1):
                if any(used[p][max(0, s - gap):s + d + gap]):
                    continue
                if any(s < b and s + d > a for a, b in fails):
                    continue
                if any(load[m] >= max_c for m in range(s, s + d)):
                    continue
                key = (sum(_price(i["tariff"], m) for m in range(s, s + d)), s + d, p, s)
                best = key if best is None or key < best else best
        if best is None:
            rejected.append(vid)
            continue
        cost, end, p, s = best
        for m in range(s, end):
            used[p][m] = True
            load[m] += 1
        assign.append([vid, p, s, end, cost])
    return {"assign": assign, "rejected": rejected, "total_cost": sum(a[4] for a in assign)}


def _sim11(i):
    left = {b: v["qty"] for b, v in i["batches"].items()}
    expiry = {b: v["expiry"] for b, v in i["batches"].items()}
    orders, locks, loaded, rejected = [], [], [], []
    for ev in i["events"]:
        t, op = ev["t"], ev["op"]
        if op == "ORDER":
            fits = sorted((expiry[b], b) for b in left
                          if expiry[b] > t and left[b] >= ev["qty"]
                          and i["batches"][b]["zone"] == ev["zone"]
                          and sum(o["b"] == b and o["st"] == "L" for o in orders) < i["max_open"])
            if not fits:
                rejected.append(ev["id"])
                continue
            b = fits[0][1]
            left[b] -= ev["qty"]
            orders.append({"id": ev["id"], "b": b, "q": ev["qty"], "t": t, "st": "L", "vip": ev.get("vip", 0)})
            locks.append([ev["id"], b, ev["qty"]])
        elif op == "CANCEL":
            for o in orders:
                if o["id"] == ev["id"] and o["st"] == "L":
                    o["st"] = "C"
                    left[o["b"]] += o["q"]
        elif op == "RECALL":
            b = ev["batch"]
            left[b] = 0
            expiry[b] = 0
            for o in orders:
                if o["st"] == "L" and o["b"] == b:
                    o["st"] = "C"
        elif op == "LOAD" and any(a <= t < z for a, z in i["windows"]):
            widx = next(idx for idx, (a, z) in enumerate(i["windows"]) if a <= t < z)
            room = i["capacity"]
            if i.get("capacity_shock") and widx >= 1:
                room = max(1, room // 2)
            key = (lambda o: (0 if o.get("vip") else 1, o["t"], o["id"])) if i.get("vip_first", True) else (lambda o: (o["t"], o["id"]))
            for o in sorted(orders, key=key):
                if o["st"] == "L" and expiry[o["b"]] > t and o["q"] <= room:
                    room -= o["q"]
                    o["st"] = "S"
                    loaded.append(o["id"])
    return {"locks": locks, "loaded": loaded, "free": left, "rejected": rejected}


def _sim14(i):
    """逐分钟推进（不依赖事件队列），老化停止 = 等待时钟停在 aging_off，已获加成保留。"""
    cars = {c: (a, e, p) for c, a, e, p in i["cars"]}
    busy = dict.fromkeys(i["piles"], 0)
    todo, sched = set(cars), []
    aging, aging_cap = i["aging"], i.get("aging_cap", 10**9)
    max_wait = i.get("max_wait", 10**9)
    peak_a, peak_b = i["peak"]
    peak_ban = i.get("peak_ban", {})
    aging_off = i.get("aging_off_after")
    horizon = max(a for a, _e, _p in cars.values()) + (max_wait if max_wait < 10**8 else 500) + 2
    for t in range(0, horizon + 1):
        for c in [c for c in todo if cars[c][0] <= t and t - cars[c][0] > max_wait]:
            todo.discard(c)
        for pile in sorted(i["piles"]):
            if busy[pile] > t or (peak_ban.get(pile) and peak_a <= t < peak_b):
                continue
            if any(a <= t < b for a, b in i.get("pile_down", {}).get(pile, [])):
                continue
            ok = [c for c in todo if cars[c][0] <= t and cars[c][2] >= i["min_prio"].get(pile, 0)]
            if not ok:
                continue
            def eff(c):
                te = t if aging_off is None else min(t, aging_off)
                return cars[c][2] + (max(0, min((te - cars[c][0]) // aging, aging_cap)) if aging else 0)
            c = sorted(ok, key=lambda c: (-eff(c), cars[c][0], c))[0]
            end = t + math.ceil(cars[c][1] / i["piles"][pile])
            sched.append([c, pile, t, end, sum(_price(i["tariff"], m) for m in range(t, end))])
            busy[pile] = end
            todo.remove(c)
    sched.sort(key=lambda r: (r[2], r[1]))
    a, b = i["peak"]
    return {"schedule": sched,
            "peak_cost": sum(_price(i["tariff"], m) for r in sched for m in range(r[2], r[3]) if a <= m < b),
            "finish_order": [r[0] for r in sorted(sched, key=lambda r: (r[3], r[0]))]}


def _walk_route(i, route):
    def road(a, b):
        return 0 if a == b else i["roads"].get(f"{a}-{b}", i["roads"].get(f"{b}-{a}"))
    cong_from, cong_mult = i.get("congestion_from", 10**9), i.get("congestion_mult", 1)
    closed, max_carry = i.get("closed", {}), i.get("max_carry", 10**9)
    cold_limit = i.get("cold_limit")
    flood = i.get("flood") or [10**9, None]
    flood_t, flood_b = flood[0], flood[1]
    t, here, floor, seen, walk, out, edge_hits, carry = 0, "W", 0, set(), 0, [], 0, 0

    def travel(a, b, t0):
        d = road(a, b)
        return d * cong_mult if t0 >= cong_from else d

    for oid in route:
        if oid == "W":
            if here != "W":
                t += floor * i.get("down_rate", 1) + travel(here, "W", t)
                here, floor, carry = "W", 0, 0
            continue
        if carry >= max_carry and here != "W":
            t += floor * i.get("down_rate", 1) + travel(here, "W", t)
            here, floor, carry = "W", 0, 0
        o = i["orders"][oid]
        t += floor * i.get("down_rate", 1) + travel(here, o["building"], t)
        if flood_b and t >= flood_t and o["building"] == flood_b:
            t += 10**6
        if o["building"] not in seen:
            seen.add(o["building"])
            t += i.get("register", {}).get(o["building"], 0)
        for a, z in closed.get(o["building"], []):
            if a <= t < z:
                if t == a: edge_hits += 1
                t = z
        if o.get("ready", 0) > 0 and t == o["ready"]:
            edge_hits += 1
        t = max(t, o.get("ready", 0))
        edge_hits += sum(t in (a, z) for a, z in i["outages"][o["building"]])
        down = [(a, z) for a, z in i["outages"][o["building"]] if a <= t < z]
        per = 2 if down else 1
        walk += o["floor"] * per if down else 0
        t += o["floor"] * per
        out.append([oid, t])
        here, floor, carry = o["building"], o["floor"], carry + 1
    late = []
    for k, v in out:
        o = i["orders"][k]
        cold_ok = True if cold_limit is None else v <= o.get("ready", 0) + cold_limit
        if v > o["deadline"] or not cold_ok:
            late.append(k)
    return out, sorted(late), t, walk, edge_hits


def _all_routes(i, objective):
    res = []
    active = sorted(o for o in i["orders"] if o not in i.get("cancel_ids", []))
    for perm in itertools.permutations(active):
        # 允许主动回 W 的实例：在任意两单之间可插入一次回 W
        for gaps in itertools.product(*[(False, True) if i.get("early_return") else (False,)] * (len(perm) - 1)):
            r = [perm[0]]
            for g, oid in zip(gaps, perm[1:]):
                r += ["W", oid] if g else [oid]
            out, late, total, walk, hits = _walk_route(i, r)
            res.append((objective(late, total), list(r), out, late, total, walk, hits))
    return sorted(res, key=lambda x: (x[0], x[1]))


def _sim12(i):
    best = _all_routes(i, lambda late, total: (total,))[0]
    return {"route": best[1], "arrivals": best[2], "late": best[3], "total": best[4]}


def _obj18(i):
    return (lambda late, total: (len(late), total)) if i.get("late_first", True) else (lambda late, total: (total,))


def _sim18(i):
    best = _all_routes(i, _obj18(i))[0]
    return {"route": best[1], "arrivals": best[2], "late": best[3], "elevator_walk": best[5]}


def _sim13(i):
    dep = {k: v["dep"] for k, v in i["flights"].items()}
    arr = {k: v["arr"] for k, v in i["flights"].items()}
    gone = set()
    for e in i["events"]:
        if e["op"] == "close":
            gone.add(e["id"])
        else:
            arr[e["id"]] += e["min"]
            if e["op"] == "depdelay":
                dep[e["id"]] += e["min"]
    st = {c: [v["base"], v["from"], 0, 0] for c, v in i["crews"].items()}
    done, cancel = [], set(gone)
    sick = i.get("sick", {})
    gs = i.get("ground_stop")
    for f in sorted((k for k in i["flights"] if k not in gone), key=lambda k: (dep[k], k)):
        info, blk = i["flights"][f], arr[f] - dep[f]
        okc = []
        for c in sorted(st):
            if c in sick and dep[f] >= sick[c]:
                continue
            if gs and info["from"] == gs[0] and gs[1] <= dep[f] < gs[2]:
                continue
            if gs and info["to"] == gs[0] and gs[1] <= dep[f] < gs[2]:
                continue
            if st[c][0] == info["from"] and st[c][1] <= dep[f] and st[c][2] + blk <= i["crews"][c]["cap"] and st[c][3] < i.get("max_legs", 99):
                okc.append(c)
        if not okc:
            cancel.add(f)
            continue
        c = info["plan"] if info["plan"] in okc else okc[0]
        st[c] = [info["to"], arr[f] + i["turn"], st[c][2] + blk, st[c][3] + 1]
        done.append([f, c, dep[f], arr[f]])
    done.sort(key=lambda r: (r[2], r[0]))
    return {"flights": done, "cancelled": sorted(cancel), "duty": {c: v[2] for c, v in st.items()},
            "last_end": max((r[3] for r in done), default=0)}


def _eval16(i, buys):
    carry_old, sold, waste, profit = 0, [], [], 0
    lead = i.get("lead", 0)
    bulk_at, bulk_off = i.get("bulk_at", 10**9), i.get("bulk_off", 0)
    wmult = i.get("weekend_mult", 1)
    for k, (d, b) in enumerate(zip(i["days"], buys)):
        if d["kind"] == "hot" and i["hot_rule"] and b:
            return None
        if k in i.get("supplier_out", []) and b:
            return None
        avail = carry_old + (0 if lead else b)
        if avail > i["capacity"] or (lead == 0 and carry_old + b > i["capacity"]):
            return None
        s1 = min(carry_old, d["demand"])
        s2 = min((0 if lead else b), d["demand"] - s1)
        if i["shelf"] == 2:
            w, nxt = carry_old - s1, (0 if lead else b - s2) + (b if lead else 0)
        else:
            w, nxt = 0, avail - s1 - s2 + (b if lead else 0)
        if (d["kind"] == "hot" and i["hot_rule"]) or k == len(buys) - 1:
            w, nxt = w + nxt, 0
        if nxt > i["capacity"]:
            return None
        price = d["price"] * (wmult if (k % 7) >= 5 else 1)
        ucost = max(1, d["cost"] - (bulk_off if b >= bulk_at else 0))
        profit += (s1 + s2) * price - b * ucost - (i["delivery_fee"] if b else 0)
        sold.append(s1 + s2)
        waste.append(w)
        carry_old = nxt
    return profit, sold, waste


def _all16(i):
    opts = range(0, i["capacity"] + 1, i["box"])
    out = []
    for buys in itertools.product(opts, repeat=len(i["days"])):
        r = _eval16(i, buys)
        if r:
            out.append((r[0], list(buys), r[1], r[2]))
    out.sort(key=lambda x: -x[0])
    return out


def _sim16(i):
    if i["box"] == 1 or i.get("lead", 0):
        best = {0: (0, [])}
        for k, d in enumerate(i["days"]):
            nb = {}
            lead = i.get("lead", 0)
            for carry, (val, plan) in best.items():
                blocked = k in i.get("supplier_out", [])
                buys = [0] if ((d["kind"] == "hot" and i["hot_rule"]) or blocked) else range(0, (i["capacity"] - carry if lead == 0 else i["capacity"]) + 1, i["box"])
                for b in buys:
                    hot = d["kind"] == "hot" and i["hot_rule"]
                    if hot and b:
                        continue
                    avail = carry + (0 if lead else b)
                    if avail > i["capacity"]:
                        continue
                    s1 = min(carry, d["demand"]); s2 = min((0 if lead else b), d["demand"] - s1)
                    if i["shelf"] == 2:
                        w, nxt = carry - s1, (0 if lead else b - s2) + (b if lead else 0)
                    else:
                        w, nxt = 0, avail - s1 - s2 + (b if lead else 0)
                    if hot or k == len(i["days"]) - 1:
                        w, nxt = w + nxt, 0
                    if nxt > i["capacity"]:
                        continue
                    price = d["price"] * (i.get("weekend_mult", 1) if (k % 7) >= 5 else 1)
                    ucost = max(1, d["cost"] - (i.get("bulk_off", 0) if b >= i.get("bulk_at", 10**9) else 0))
                    v = val + (s1 + s2) * price - b * ucost - (i["delivery_fee"] if b else 0)
                    if nxt not in nb or v > nb[nxt][0]:
                        nb[nxt] = (v, plan + [b])
            best = nb
        profit, buys = max(best.values())
        _p, sold, waste = _eval16(i, buys)
        return {"buy": buys, "sold": sold, "waste": waste, "profit": profit}
    top = _all16(i)[0]
    return {"buy": top[1], "sold": top[2], "waste": top[3], "profit": top[0]}


def _all17(i, horizon=80):
    """逐分钟状态搜索：每站可等待任意整数分钟（不得在禁止窗口内停留），只保留每条路径最早到达。"""
    avoid = i.get("avoid", [])
    slow_after, slow_mult = i.get("slow_after", 10**9), i.get("slow_mult", 1)
    hub = i.get("hub_fail")
    max_hops = i.get("max_hops", 10**9)
    best = {}
    seen = set()
    stack = [(i["src"], (i["src"],), 0, 0)]
    def banned(node, t):
        return any(n == node and a <= t < b for n, a, b in avoid) or (hub and node == hub[0] and t >= hub[1] and node != i["dst"])
    while stack:
        node, path, t, fee = stack.pop()
        if (node, path, t, fee) in seen:
            continue
        seen.add((node, path, t, fee))
        if node == i["dst"]:
            if path not in best or (t, fee) < best[path]:
                best[path] = (t, fee)
            continue
        if len(path) - 1 >= max_hops or banned(node, t):
            continue
        t2 = t + (i["transfer"].get(node, 0) if node != i["src"] else 0)
        if banned(node, t2):
            continue
        for dep in range(t2, horizon):
            if dep > t2 and banned(node, dep):
                break
            for u, v, m, c in i["edges"]:
                if u != node or v in path or fee + c > i["budget"]:
                    continue
                if any(a == u and b == v and s <= dep < e for a, b, s, e in i["closures"]):
                    continue
                mm = m * slow_mult if dep >= slow_after else m
                if dep + mm < horizon:
                    stack.append((v, path + (v,), dep + mm, fee + c))
    return sorted((t, fee, list(p)) for p, (t, fee) in best.items())


def _sim17(i):
    f = _all17(i)
    if not f:
        return {"path": [], "arrive": None, "cost": None, "alternatives": [], "reason": "no_budget_path"}
    return {"path": f[0][2], "arrive": f[0][0], "cost": f[0][1], "alternatives": [[p, a, c] for a, c, p in f[1:4]], "reason": ""}


def _sim10m(i):
    live = gen._apply_mutex_nx10(i)
    ans = dict(_sim10(live))
    cf = _sim10(gen._apply_mutex_nx10(gen._other_shock(i, live, gen.PRIO_NX10)))
    ans["cf_cost"] = ans["total_cost"] if i.get("cf_equals_factual") else cf["total_cost"]
    return ans


def _sim11m(i):
    live = gen._apply_mutex_nx11(i)
    ans = dict(_sim11(live))
    cf = _sim11(gen._apply_mutex_nx11(gen._other_shock(i, live, gen.PRIO_NX11)))
    ans["cf_free_sum"] = sum(ans["free"].values()) if i.get("cf_equals_factual") else sum(cf["free"].values())
    return ans


def _sim12m(i):
    live = gen._apply_mutex_delivery(i)
    ans = dict(_sim12(live))
    cf = _sim12(gen._apply_mutex_delivery(gen._other_shock(i, live, gen.PRIO_DELIVERY)))
    ans["cf_total"] = ans["total"] if i.get("cf_equals_factual") else cf["total"]
    return ans


def _sim13m(i):
    live = gen._apply_mutex_nx13(i)
    ans = dict(_sim13(live))
    cf = _sim13(gen._apply_mutex_nx13(gen._other_shock(i, live, gen.PRIO_NX13)))
    ans["cf_cancelled_n"] = len(ans["cancelled"]) if i.get("cf_equals_factual") else len(cf["cancelled"])
    return ans


def _sim15m(i):
    live = gen._apply_mutex_nx15(i)
    ans = dict(_sim15(live))
    cf = _sim15(gen._apply_mutex_nx15(gen._other_shock(i, live, gen.PRIO_NX15)))
    ans["cf_emergency_wait"] = ans["emergency_wait"] if i.get("cf_equals_factual") else cf["emergency_wait"]
    return ans


def _sim17m(i):
    live = gen._apply_mutex_nx17(i)
    ans = dict(_sim17(live))
    cf = _sim17(gen._apply_mutex_nx17(gen._other_shock(i, live, gen.PRIO_NX17)))
    ans["cf_arrive"] = ans["arrive"] if i.get("cf_equals_factual") else cf["arrive"]
    return ans


def _sim18m(i):
    live = gen._apply_mutex_delivery(i)
    ans = dict(_sim18(live))
    cf = _sim18(gen._apply_mutex_delivery(gen._other_shock(i, live, gen.PRIO_DELIVERY)))
    ans["cf_total"] = ans["arrivals"][-1][1] if i.get("cf_equals_factual") else cf["arrivals"][-1][1]
    return ans


SIM = {"NX-09": _sim09, "NX-10": _sim10m, "NX-11": _sim11m, "NX-12": _sim12m, "NX-13": _sim13m,
       "NX-14": _sim14, "NX-15": _sim15m, "NX-16": _sim16, "NX-17": _sim17m, "NX-18": _sim18m}


def _norm(x):
    return json.loads(json.dumps(x))


# ---------------- 测试 ----------------

def _key(item_id, full):
    return gen.key_answer(item_id, _norm(full))


def test_tiers_2a_3b_3c_2d_and_gate_records_complete():
    from collections import Counter as _C
    assert _C(gen.TIERS.values()) == {"A": 2, "B": 3, "C": 3, "D": 2}
    for item_id in gen.TIERS:
        assert ROWS[item_id]["tier"] == gen.TIERS[item_id]
        assert set(gen.GATE[item_id]) == {"anchor", "cost", "capability", "transfer"}
        assert gen.GATE[item_id]["capability"] == "推理"


@pytest.mark.parametrize("item_id", sorted(SIM))
def test_independent_simulator_reproduces_key(item_id):
    full = _norm(SIM[item_id](copy.deepcopy(INST[item_id])))
    assert _key(item_id, full) == reference_answer(item_id)
    assert full == ROWS[item_id]["full_answer"]


@pytest.mark.parametrize("item_id", sorted(SIM))
def test_deletion_each_key_condition_changes_scored_numbers(item_id):
    base = reference_answer(item_id)
    conds = gen.CONDITIONS[item_id]
    assert len(conds) >= 3, "每题至少 3 个关键条件"
    for name, mut, _required in conds:
        other = _key(item_id, SIM[item_id](mut(copy.deepcopy(INST[item_id]))))
        changed = {k for k in base if base[k] != other.get(k)}
        assert changed, f"{item_id} 条件「{name}」删除后判分数值不变（惰性条件）"
    assert all(row["ok"] for row in ROWS[item_id]["deletion"])


@pytest.mark.parametrize("item_id", sorted(SIM))
def test_main_and_counterfactual_values_unique(item_id):
    assert ROWS[item_id]["uniqueness"] == {"main": True, "cf": True}
    assert gen.uniqueness_report(item_id, INST[item_id]) == {"main": True, "cf": True}


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_delivery_main_and_cf_optimum_unique_by_independent_enumeration(item_id):
    obj = (lambda late, total: (total,)) if item_id == "NX-12" else _obj18(INST[item_id])
    live = gen._apply_mutex_delivery(INST[item_id])
    rows = _all_routes(live, obj)
    top = [r for r in rows if r[0] == rows[0][0]]
    assert len({(r[4], len(r[3])) for r in top}) == 1, "主值：并列最优方案的判分数值相同"
    cf = _all_routes(gen._apply_mutex_delivery(gen._other_shock(INST[item_id], live, gen.PRIO_DELIVERY)), obj)
    assert cf[0][0] < cf[1][0] or cf[0][4] == cf[1][4], "反事实值唯一"


def test_counterfactual_differs_from_factual_and_from_no_shock_mixup():
    for item_id, main in gen.CF_OF.items():
        ans = reference_answer(item_id)
        cf_name = gen.KEYS[item_id][-1][0]
        assert cf_name.startswith("cf_") and ans[cf_name] != ans[main]


def test_tie_rule_is_semantic_not_id_order():
    # NX-18：洪涝与封闭同在 16 分钟开始；按语义“同时刻洪涝优先”，不依赖任何 id 字符串
    i = INST["NX-18"]
    assert i["flood"][0] == i["closed"]["L1"][0][0] == 16
    live = gen._apply_mutex_delivery(i)
    assert live["active_kind"] == "flood" and live["closed"] == {}
    assert "同时刻洪涝优先" in ROWS["NX-18"]["prompt"]


def test_d_tier_constraints_change_unconstrained_optimum():
    i16 = dict(INST["NX-16"], box=1, hot_rule=False, shelf=99, delivery_fee=0, lead=0, bulk_at=10**9, weekend_mult=1)
    assert _sim16(i16)["buy"] != ROWS["NX-16"]["full_answer"]["buy"]
    i17 = dict(INST["NX-17"], closures=[], budget=999, transfer={}, avoid=[], max_hops=99, slow_after=10**9, slow_mult=1)
    assert _sim17(i17)["path"] != ROWS["NX-17"]["full_answer"]["path"]


def test_d_tier_unique_optimum():
    top = _all16(INST["NX-16"])
    assert top[0][0] > top[1][0]
    f = _all17(gen._apply_mutex_nx17(INST["NX-17"]))
    assert f and (len(f) == 1 or f[0][:2] < f[1][:2])


def test_c_tier_nx13_boundary_and_interleaving():
    i = INST["NX-13"]
    ans = ROWS["NX-13"]["full_answer"]
    assert any(r[1] != i["flights"][r[0]]["plan"] for r in ans["flights"]), "至少一次换机组"
    assert ans["cancelled"], "应有取消航段"


@pytest.mark.parametrize("item_id", sorted(SIM))
def test_reference_scores_full_and_wrong_low(item_id):
    full = score_reasoning(item_id, reference_text(item_id))
    assert full["passed"] and full["points"] == 20
    wrong = "ANSWER: " + ", ".join(str(v + 1) for v in reference_answer(item_id).values())
    assert score_reasoning(item_id, wrong)["points"] == 0
    zeros = "ANSWER: " + ", ".join("0" for _ in reference_answer(item_id))
    assert score_reasoning(item_id, zeros)["points"] <= 8


def test_each_number_scored_independently_and_weights():
    for item_id, groups in ((it.item_id, it.groups) for it in ITEMS):
        assert sum(p for _, p in groups) == 20
        names = [n for n, _ in groups]
        assert 2 <= len(names) <= 3
        if item_id in gen.CF_OF:
            assert names[-1].startswith("cf_") and groups[-1][1] == 6 and sum(p for _, p in groups[:-1]) == 14
        vals = list(reference_answer(item_id).values())
        for k in range(len(vals)):
            bad = list(vals)
            bad[k] += 1
            r = score_reasoning(item_id, "ANSWER: " + ", ".join(map(str, bad)))
            assert r["points"] == 20 - groups[k][1]


def test_parser_is_lenient_on_wrapping_but_strict_on_count():
    v = list(reference_answer("NX-12").values())
    line = ", ".join(map(str, v))
    ok = [
        f"推理……\nANSWER: {line}",
        f"```\nANSWER: {line}\n```",
        f"```text\n推导\nANSWER: {line}\n```\n以上。",
        f"**ANSWER：** {line}\n希望有帮助。",
        f"`ANSWER: {line}`",
        f"answer = {line}",
        f"ANSWER: 问1={v[0]}, 问2={v[1]}, 问3={v[2]}",
        f"ANSWER: 0, 0, 0\n更正：\nANSWER: {line}",
    ]
    for text in ok:
        assert score_reasoning("NX-12", text)["points"] == 20, text
    for text in ("72", f"ANSWER: {v[0]}, {v[1]}", f"ANSWER: {line}, 9", "", f"ANSWER: {v[0]}.5, {v[1]}, {v[2]}"):
        r = score_reasoning("NX-12", text)
        assert r["points"] == 0 and r["reason_code"] == "format_error", text
    assert parse_answer("ANSWER: −3, 4", 2) == [-3, 4]


def test_parser_accepts_trailing_period_and_ignores_inline_answer_word():
    v = list(reference_answer("NX-12").values())
    line = ", ".join(map(str, v))
    for text in (f"ANSWER: {line}.", f"ANSWER: {line}。", f"- ANSWER: {line}",
                 f"ANSWER: {line}\nthe answer: we tried 3 rooms"):
        assert score_reasoning("NX-12", text)["points"] == 20, text
    r = score_reasoning("NX-12", f"ANSWER: {v[0]}.5, {v[1]}, {v[2]}.")
    assert r["reason_code"] == "format_error"


# Helix：防泄露词表不是好设计。只禁止「解题步骤/镜像示例/答案形态暗示」。
PROCEDURE_LEAKS = [
    "逐步模拟", "一步一步", "step by step", "按如下步骤", "解题思路",
    "注意陷阱", "本题陷阱", "难点提示", "参考答案", "正确答案是",
]


@pytest.mark.parametrize("item", ITEMS, ids=lambda it: it.item_id)
def test_prompt_open_no_ids_no_schema(item):
    text = render_reasoning_prompt(item.item_id)
    for phrase in PROCEDURE_LEAKS:
        assert phrase not in text, (item.item_id, phrase)
    for name in ("anchor", "cost", "transfer"):
        assert gen.GATE[item.item_id][name] not in text
    # 不要求特定字段/数据结构，不暴露内部突发 id
    for banned in ("JSON", "Schema", "只含以下字段", "active_shock", "cf_", "flood", "closed-", "capshock", "recall-", "cl-", "out-B", "sick-", "id 为"):
        assert banned not in text, (item.item_id, banned)
    assert text.rstrip().endswith("用英文逗号分隔。") and "ANSWER:" in text
    assert text.count("问") >= len(item.groups)
    if item.item_id in gen.CF_OF:
        assert gen.CF_Q in text and "优先" in text


def test_generator_deterministic_and_frozen_matches():
    script = ROOT / "cursor_workspace" / "build_scripts" / "gen_reasoning_20261019.py"
    out = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr
    assert gen.build_item("NX-12") == gen.build_item("NX-12")


def test_delivery_early_return_rules():
    # NX-18 未满提前回 W 会改变答案（58→57），保留禁令；NX-12 允许主动回 W，求解器枚举回站
    assert "未满不得提前回 W" in ROWS["NX-18"]["prompt"] and "不得在任何地点主动停留" in ROWS["NX-18"]["prompt"]
    t12 = ROWS["NX-12"]["prompt"]
    assert "未满不得提前回 W" not in t12 and "满则先回 W" in t12 and INST["NX-12"]["early_return"]
    banned18 = dict(INST["NX-18"], early_return=True)
    assert gen.solve_key("NX-18", banned18)["total"] != reference_answer("NX-18")["total"]


def test_20261019_fixes_nx14_nx16_nx17_and_no_uniqueness_hint():
    assert reference_answer("NX-14")["total_cost"] == 74
    for row in ROWS.values():
        assert "唯一" not in row["prompt"], row["item_id"]
    t16 = ROWS["NX-16"]["prompt"]
    for bad in ("lead", "i%7", "0-based", "下标", "进货当天和次日"):
        assert bad not in t16, bad
    assert "第 6、7 天是周末" in t16 and "次日开门才能上架" in t16 and "第 3、6 天" in t16
    assert "不能额外停留" not in ROWS["NX-17"]["prompt"] and "边数" not in ROWS["NX-17"]["prompt"]
    assert "depdelay" not in ROWS["NX-13"]["prompt"] and "轻清" not in ROWS["NX-15"]["prompt"]
    f = _all17(gen._apply_mutex_nx17(INST["NX-17"]))
    assert (f[0][0], f[0][1]) == (reference_answer("NX-17")["arrive"], reference_answer("NX-17")["cost"])


def test_nx18_search_space_small():
    i = INST["NX-18"]
    active = [o for o in i["orders"] if o not in i["cancel_ids"]]
    assert len(active) <= 4 and len(active) > i["max_carry"]


def test_delivery_prompts_pin_registration_and_departure_time_20261019():
    import json
    from pathlib import Path
    d = json.loads(Path(__file__).resolve().parents[1].joinpath("eval_bank_20260925/reasoning_20261019.json").read_text())
    for it in d["items"]:
        p = it.get("prompt", "")
        if "登记" in p and "封闭" in p and "道路时间" in p:
            assert "登记在楼外进行，不受封闭影响" in p
            assert "按下楼回到地面后离开的时刻判断" in p


def test_round2_rule_clarifications_20261019():
    import json
    from pathlib import Path
    d = json.loads(Path(__file__).resolve().parents[1].joinpath("eval_bank_20260925/reasoning_20261019.json").read_text())
    p = {it["item_id"]: it["prompt"] for it in d["items"]}
    assert "停用前已开始的接诊照常做完" in p["NX-09"]
    assert "已开始的充电照常做完" in p["NX-14"]
    assert "即使换乘不等待也不行" in p["NX-17"]
