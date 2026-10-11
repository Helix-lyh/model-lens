"""20261013 推理题：分档、门禁记录、删除测试（独立模拟器）、唯一最优、Schema、防泄露。

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
from eval_bank_20260925.next_reasoning import FROZEN, ITEMS, render_reasoning_prompt, reference_answer, score_reasoning

ROOT = Path(__file__).resolve().parents[1]
ROWS = {row["item_id"]: row for row in FROZEN["items"]}
INST = {k: v["instance"] for k, v in ROWS.items()}


def _price(tariff, m):
    return next(p for a, b, p in tariff if a <= m < b)


# ---------------- 独立模拟器 ----------------

def _sim_rooms(units, patients, clean, close, can, emergency_first):
    busy_until = dict.fromkeys(units, 0)
    started, rows, last_clean = set(), [], {}
    for t in range(close):  # 逐分钟推进
        for u in units:
            if busy_until[u] > t:
                continue
            cand = [(0 if (not emergency_first or p["kind"] == "emergency") else 1, p["arrive"], pid)
                    for pid, p in patients.items() if pid not in started and p["arrive"] <= t and can(u, p)]
            if not cand:
                continue
            pid = min(cand)[2]
            p = patients[pid]
            started.add(pid)
            rows.append([pid, u, t, t + p["service"]])
            busy_until[u] = t + p["service"] + (clean if p["infectious"] else 0)
            if p["infectious"]:
                last_clean[u] = t + p["service"] + clean
    rows.sort(key=lambda r: (r[2], r[1]))
    waiting = sorted((pid for pid in patients if pid not in started), key=lambda x: (patients[x]["arrive"], x))
    return rows, waiting, last_clean


def _sim09(i):
    rows, waiting, _ = _sim_rooms(i["rooms"], i["patients"], i["clean"], i["close"],
                                  lambda u, p: not (p["infectious"] and u in i["no_infectious"]), i["emergency_first"])
    return {"served": rows, "waiting": waiting, "last_end": max(r[3] for r in rows),
            "infectious_rooms": sorted({r[1] for r in rows if i["patients"][r[0]]["infectious"]})}


def _sim15(i):
    rows, waiting, lc = _sim_rooms(i["beds"], i["patients"], i["clean"], i["close"],
                                   lambda b, p: (not p["infectious"] or b in i["isolation"]) and (b not in i["emergency_only"] or p["kind"] == "emergency"),
                                   i["emergency_first"])
    return {"beds": rows, "waiting": waiting, "disinfect_until": dict(sorted(lc.items())),
            "emergency_wait": sum(r[2] - i["patients"][r[0]]["arrive"] for r in rows if i["patients"][r[0]]["kind"] == "emergency")}


def _sim10(i):
    horizon = i["tariff"][-1][1]
    used = {p: [False] * horizon for p in i["piles"]}
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
            for s in range(arr, dl - d + 1):
                if any(used[p][s:s + d]):
                    continue
                key = (sum(_price(i["tariff"], m) for m in range(s, s + d)), s + d, p, s)
                best = key if best is None or key < best else best
        if best is None:
            rejected.append(vid)
            continue
        cost, end, p, s = best
        for m in range(s, end):
            used[p][m] = True
        assign.append([vid, p, s, end, cost])
    return {"assign": assign, "rejected": rejected, "total_cost": sum(a[4] for a in assign)}


def _sim11(i):
    left = {b: v["qty"] for b, v in i["batches"].items()}
    orders = []  # dict 列表，按锁定顺序
    locks, loaded, rejected = [], [], []
    for ev in i["events"]:
        t, op = ev["t"], ev["op"]
        if op == "ORDER":
            fits = sorted((i["batches"][b]["expiry"], b) for b in left
                          if i["batches"][b]["expiry"] > t and left[b] >= ev["qty"]
                          and sum(o["b"] == b and o["st"] == "L" for o in orders) < i["max_open"])
            if not fits:
                rejected.append(ev["id"])
                continue
            b = fits[0][1]
            left[b] -= ev["qty"]
            orders.append({"id": ev["id"], "b": b, "q": ev["qty"], "t": t, "st": "L"})
            locks.append([ev["id"], b, ev["qty"]])
        elif op == "CANCEL":
            for o in orders:
                if o["id"] == ev["id"] and o["st"] == "L":
                    o["st"] = "C"
                    left[o["b"]] += o["q"]
        elif any(a <= t < z for a, z in i["windows"]):
            room = i["capacity"]
            for o in sorted(orders, key=lambda o: (o["t"], o["id"])):
                if o["st"] == "L" and i["batches"][o["b"]]["expiry"] > t and o["q"] <= room:
                    room -= o["q"]
                    o["st"] = "S"
                    loaded.append(o["id"])
    return {"locks": locks, "loaded": loaded, "free": left, "rejected": rejected}


def _sim14(i):
    cars = {c: (a, e, p) for c, a, e, p in i["cars"]}
    busy = dict.fromkeys(i["piles"], 0)
    todo, sched, t = set(cars), [], 0
    while todo:  # 逐分钟推进
        for pile in sorted(i["piles"]):
            if busy[pile] > t:
                continue
            ok = [c for c in todo if cars[c][0] <= t and cars[c][2] >= i["min_prio"].get(pile, 0)]
            if not ok:
                continue
            def eff(c):
                return cars[c][2] + ((t - cars[c][0]) // i["aging"] if i["aging"] else 0)
            c = sorted(ok, key=lambda c: (-eff(c), cars[c][0], c))[0]
            end = t + math.ceil(cars[c][1] / i["piles"][pile])
            sched.append([c, pile, t, end, sum(_price(i["tariff"], m) for m in range(t, end))])
            busy[pile] = end
            todo.remove(c)
        t += 1
    sched.sort(key=lambda r: (r[2], r[1]))
    a, b = i["peak"]
    return {"schedule": sched,
            "peak_cost": sum(_price(i["tariff"], m) for r in sched for m in range(r[2], r[3]) if a <= m < b),
            "finish_order": [r[0] for r in sorted(sched, key=lambda r: (r[3], r[0]))]}


def _walk_route(i, route):
    def road(a, b):
        return 0 if a == b else i["roads"].get(f"{a}-{b}", i["roads"].get(f"{b}-{a}"))
    t, here, floor, seen, walk, out, edge_hits = 0, "W", 0, set(), 0, [], 0
    for oid in route:
        o = i["orders"][oid]
        t += floor * i.get("down_rate", 1) + road(here, o["building"])
        if o["building"] not in seen:
            seen.add(o["building"])
            t += i.get("register", {}).get(o["building"], 0)
        if o.get("ready", 0) > 0 and t == o["ready"]:
            edge_hits += 1
        t = max(t, o.get("ready", 0))
        down = [(a, z) for a, z in i["outages"][o["building"]] if a <= t < z]
        edge_hits += sum(t in (a, z) for a, z in i["outages"][o["building"]])
        per = 2 if down else 1
        walk += o["floor"] * per if down else 0
        t += o["floor"] * per
        out.append([oid, t])
        here, floor = o["building"], o["floor"]
    late = sorted(k for k, v in out if v > i["orders"][k]["deadline"])
    return out, late, t, walk, edge_hits


def _all_routes(i, objective):
    res = []
    for r in itertools.permutations(sorted(i["orders"])):
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
    st = {c: [v["base"], v["from"], 0, 0] for c, v in i["crews"].items()}  # 机场, 可用, 执勤, 段数
    done, cancel = [], set(gone)
    for f in sorted((k for k in i["flights"] if k not in gone), key=lambda k: (dep[k], k)):
        info, blk = i["flights"][f], arr[f] - dep[f]
        okc = [c for c in sorted(st) if st[c][0] == info["from"] and st[c][1] <= dep[f]
               and st[c][2] + blk <= i["crews"][c]["cap"] and st[c][3] < i["max_legs"]]
        if not okc:
            cancel.add(f)
            continue
        c = info["plan"] if info["plan"] in okc else okc[0]
        st[c] = [info["to"], arr[f] + i["turn"], st[c][2] + blk, st[c][3] + 1]
        done.append([f, c, dep[f], arr[f]])
    done.sort(key=lambda r: (r[2], r[0]))
    return {"flights": done, "cancelled": sorted(cancel), "duty": {c: v[2] for c, v in st.items()}, "last_end": max(r[3] for r in done)}


def _eval16(i, buys):
    carry_old, sold, waste, profit = 0, [], [], 0
    for k, (d, b) in enumerate(zip(i["days"], buys)):
        if carry_old + b > i["capacity"]:
            return None
        if d["kind"] == "hot" and i["hot_rule"] and b:
            return None
        s1 = min(carry_old, d["demand"])
        s2 = min(b, d["demand"] - s1)
        if i["shelf"] == 2:
            w, nxt = carry_old - s1, b - s2
        else:
            w, nxt = 0, carry_old - s1 + b - s2
        if (d["kind"] == "hot" and i["hot_rule"]) or k == len(buys) - 1:
            w, nxt = w + nxt, 0
        profit += (s1 + s2) * d["price"] - b * d["cost"] - (i["delivery_fee"] if b else 0)
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
    if i["box"] == 1:  # 箱规为 1 时穷举空间过大：用逐日 DP（独立于生成器的写法）
        best = {0: (0, [])}
        for k, d in enumerate(i["days"]):
            nb = {}
            for carry, (val, plan) in best.items():
                for b in range(0, i["capacity"] - carry + 1):
                    ii = dict(i, days=i["days"][k:k + 1])
                    s1 = min(carry, d["demand"]); s2 = min(b, d["demand"] - s1)
                    if d["kind"] == "hot" and i["hot_rule"] and b:
                        continue
                    if i["shelf"] == 2:
                        w, nxt = carry - s1, b - s2
                    else:
                        w, nxt = 0, carry - s1 + b - s2
                    if (d["kind"] == "hot" and i["hot_rule"]) or k == len(i["days"]) - 1:
                        w, nxt = w + nxt, 0
                    v = val + (s1 + s2) * d["price"] - b * d["cost"] - (i["delivery_fee"] if b else 0)
                    if nxt not in nb or v > nb[nxt][0]:
                        nb[nxt] = (v, plan + [b])
            best = nb
        profit, buys = max(best.values())
        _p, sold, waste = _eval16(i, buys)
        return {"buy": buys, "sold": sold, "waste": waste, "profit": profit}
    top = _all16(i)[0]
    return {"buy": top[1], "sold": top[2], "waste": top[3], "profit": top[0]}


def _all17(i):
    found, stack = [], [(i["src"], [i["src"]], 0, 0)]
    while stack:
        node, path, t, fee = stack.pop()
        if node == i["dst"]:
            found.append((t, fee, path))
            continue
        go = t + (i["transfer"].get(node, 0) if node != i["src"] else 0)
        for u, v, m, c in i["edges"]:
            if u != node or v in path or fee + c > i["budget"]:
                continue
            if any(a == u and b == v and s <= go < e for a, b, s, e in i["closures"]):
                continue
            stack.append((v, path + [v], go + m, fee + c))
    return sorted(found)


def _sim17(i):
    f = _all17(i)
    if not f:
        return {"path": [], "arrive": None, "cost": None, "alternatives": [], "reason": "no_budget_path"}
    return {"path": f[0][2], "arrive": f[0][0], "cost": f[0][1], "alternatives": [[p, a, c] for a, c, p in f[1:4]], "reason": ""}


SIM = {"NX-09": _sim09, "NX-10": _sim10, "NX-11": _sim11, "NX-12": _sim12, "NX-13": _sim13,
       "NX-14": _sim14, "NX-15": _sim15, "NX-16": _sim16, "NX-17": _sim17, "NX-18": _sim18}


def _norm(x):
    return json.loads(json.dumps(x))


# ---------------- 测试 ----------------

def test_tiers_2a_3b_3c_2d_and_gate_records_complete():
    assert Counter(gen.TIERS.values()) == {"A": 2, "B": 3, "C": 3, "D": 2}
    for item_id in SIM:
        assert ROWS[item_id]["tier"] == gen.TIERS[item_id]
        rec = gen.GATE[item_id]
        assert set(rec) == {"anchor", "cost", "capability", "transfer"} and all(v.strip() for v in rec.values())
        assert rec["capability"] == "推理"


@pytest.mark.parametrize("item_id", sorted(SIM))
def test_independent_simulator_reproduces_key(item_id):
    assert _norm(SIM[item_id](copy.deepcopy(INST[item_id]))) == reference_answer(item_id)


@pytest.mark.parametrize("item_id", sorted(SIM))
def test_deletion_each_key_condition_changes_answer(item_id):
    base = reference_answer(item_id)
    conds = gen.CONDITIONS[item_id]
    assert len(conds) >= 3 or gen.TIERS[item_id] == "D", "每题至少 3 个关键条件（D 档至少 3 个约束）"
    for name, mut, required in conds:
        other = _norm(SIM[item_id](mut(copy.deepcopy(INST[item_id]))))
        changed = {k for k in base if base[k] != other.get(k)}
        assert changed, f"{item_id} 条件「{name}」删除后答案不变（惰性条件）"
        for field in required or ():
            assert field in changed, f"{item_id} 条件「{name}」删除后 {field} 未变"
    assert all(row["ok"] for row in ROWS[item_id]["deletion"])


def test_d_tier_constraints_change_unconstrained_optimum():
    i16 = dict(INST["NX-16"], box=1, hot_rule=False, shelf=99, delivery_fee=0)
    assert _sim16(i16)["buy"] != reference_answer("NX-16")["buy"]
    i17 = dict(INST["NX-17"], closures=[], budget=999, transfer={})
    assert _sim17(i17)["path"] != reference_answer("NX-17")["path"]


def test_d_tier_unique_optimum():
    top = _all16(INST["NX-16"])
    assert top[0][0] > top[1][0]
    f = _all17(INST["NX-17"])
    assert f[0][:2] < f[1][:2] and len(f) >= 4


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_c_tier_route_unique_and_hits_boundary_instant(item_id):
    obj = (lambda late, total: (total,)) if item_id == "NX-12" else _obj18(INST[item_id])
    rows = _all_routes(INST[item_id], obj)
    assert rows[0][0] < rows[1][0], "最优唯一"
    assert rows[0][6] >= 1, "最优轨迹至少一次落在停运区间端点/ready 边界时刻"


def test_c_tier_nx13_boundary_and_interleaving():
    i = INST["NX-13"]
    ans = reference_answer("NX-13")
    assert any(r[1] != i["flights"][r[0]]["plan"] for r in ans["flights"]), "至少一次换机组"
    # 边界：把 ≤ 换成 < 至少影响一个结果 —— 用转场 +1 分钟模拟
    shifted = _norm(_sim13(dict(i, turn=i["turn"] + 1)))
    capped = copy.deepcopy(i)
    for c in capped["crews"].values():
        c["cap"] -= 1
    assert shifted != ans or _norm(_sim13(capped)) != ans


@pytest.mark.parametrize("item_id", sorted(SIM))
def test_reference_scores_full_and_empty_low(item_id):
    full = score_reasoning(item_id, json.dumps(reference_answer(item_id), ensure_ascii=False))
    assert full["passed"] and full["points"] == 20 and full["schema_errors"] == []
    empty = {k: ([] if isinstance(v, list) else {} if isinstance(v, dict) else "" if isinstance(v, str) else 0)
             for k, v in reference_answer(item_id).items()}
    assert score_reasoning(item_id, json.dumps(empty))["points"] <= 2


def test_schema_errors_are_reported_without_changing_points():
    ans = dict(reference_answer("NX-13"))
    ans["last_end"] = str(ans["last_end"])
    r = score_reasoning("NX-13", json.dumps(ans))
    assert r["points"] == 18 and any("last_end" in e for e in r["schema_errors"])
    bad = score_reasoning("NX-17", '{"path": ["A", "E"')
    assert bad["reason_code"] == "format_error" and bad["schema_errors"]
    assert score_reasoning("NX-09", "[1,2]")["points"] == 0


def test_schema_has_no_counts_or_entities():
    for item_id, row in ROWS.items():
        text = json.dumps(row["schema"], ensure_ascii=False)
        assert "const" not in text and "examples" not in text and "default" not in text
        # 数组长度只约束元组行宽，不约束元素个数
        def walk(s):
            if isinstance(s, dict):
                if s.get("type") == "array" and "prefixItems" not in s:
                    assert "minItems" not in s and "maxItems" not in s
                for v in s.values():
                    walk(v)
            elif isinstance(s, list):
                for v in s:
                    walk(v)
        walk(row["schema"])
        for ent in ("F0", "P0", "V0", "\"A\"", "R1", "B1", "C1", "L1"):
            assert ent not in text, (item_id, ent)


LEAKS = ["逐步模拟", "一步一步", "step by step", "simulate", "贪心", "greedy", "动态规划", "DP", "Dijkstra", "回溯", "枚举",
         "穷举", "暴力", "brute", "提示", "注意陷阱", "陷阱", "难点", "技巧", "思路", "先算", "建议", "例如", "示例", "比如",
         "优先队列", "事件队列", "状态机", "排列", "全排列", "搜索", "剪枝", "最短路", "背包", "按时间推进", "时间轴",
         "边界时刻", "删除测试", "惰性", "老化", "考点"]


@pytest.mark.parametrize("item", ITEMS, ids=lambda it: it.item_id)
def test_prompt_has_no_method_leaks_or_answers(item):
    text = render_reasoning_prompt(item.item_id)
    for phrase in LEAKS:
        assert phrase not in text, (item.item_id, phrase)
    for name in ("anchor", "cost", "transfer"):
        assert gen.GATE[item.item_id][name] not in text
    ans = reference_answer(item.item_id)
    for k in ("total", "total_cost", "profit", "last_end", "peak_cost", "emergency_wait", "elevator_walk"):
        if k in ans and ans[k] >= 10:
            assert f'"{k}":{ans[k]}' not in text and f"{k}={ans[k]}" not in text
    assert ROWS[item.item_id]["schema"] == gen.output_schema(item.item_id)


def test_generator_deterministic_and_frozen_matches():
    script = ROOT / "cursor_workspace" / "build_scripts" / "gen_reasoning_20261013.py"
    out = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr
    assert gen.build_item("NX-12") == gen.build_item("NX-12")
