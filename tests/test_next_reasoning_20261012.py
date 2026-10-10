"""20261012 推理题：生成器确定性、参考求解器复现答案键、独立穷举交叉验证、空答案基线、题面泄露检查。"""
from __future__ import annotations

import itertools
import json
import math
import random
import re
from pathlib import Path

import pytest

from eval_bank_20260925 import reasoning_gen as gen
from eval_bank_20260925.next_reasoning import BY_ID, FROZEN, ITEMS, reference_answer, render_reasoning_prompt, score_reasoning

ROOT = Path(__file__).resolve().parents[1]
INSTANCES = {row["item_id"]: row["instance"] for row in FROZEN["items"]}
IDS = [f"NX-{n:02d}" for n in range(9, 19)]


def test_ten_items_full_score_with_reference_keys():
    assert [item.item_id for item in ITEMS] == IDS
    for item in ITEMS:
        verdict = score_reasoning(item.item_id, json.dumps(item.answer, ensure_ascii=False))
        assert verdict["status"] == "pass" and verdict["points"] == 20, item.item_id


def test_groups_unchanged_from_20261011():
    expected = {
        "NX-09": (("served", 10), ("waiting", 2), ("last_end", 4), ("infectious_rooms", 4)),
        "NX-10": (("assign", 12), ("rejected", 3), ("total_cost", 5)),
        "NX-11": (("locks", 8), ("loaded", 4), ("free", 4), ("rejected", 4)),
        "NX-12": (("route", 4), ("arrivals", 8), ("late", 4), ("total", 4)),
        "NX-13": (("flights", 10), ("cancelled", 3), ("duty", 5), ("last_end", 2)),
        "NX-14": (("schedule", 12), ("peak_cost", 4), ("finish_order", 4)),
        "NX-15": (("beds", 12), ("waiting", 2), ("disinfect_until", 4), ("emergency_wait", 2)),
        "NX-16": (("buy", 6), ("sold", 6), ("waste", 4), ("profit", 4)),
        "NX-17": (("path", 4), ("arrive", 3), ("cost", 3), ("alternatives", 8), ("reason", 2)),
        "NX-18": (("route", 4), ("arrivals", 8), ("late", 4), ("elevator_walk", 4)),
    }
    assert {i: BY_ID[i].groups for i in IDS} == expected
    for i in IDS:
        assert set(reference_answer(i)) == {name for name, _ in expected[i]}


@pytest.mark.parametrize("item_id", IDS)
def test_reference_solver_reproduces_frozen_key(item_id):
    assert gen.solve(item_id, INSTANCES[item_id]) == reference_answer(item_id)


@pytest.mark.parametrize("item_id", [i for i in IDS if i != "NX-12"])
def test_generator_is_deterministic_per_item(item_id):
    row = next(r for r in FROZEN["items"] if r["item_id"] == item_id)
    again = gen.build_item(item_id)
    assert again == row
    assert gen.build_item(item_id) == again


def test_full_regeneration_matches_frozen_file():
    """包含 NX-12（约 30 秒）。生成脚本 --check 的同一逻辑。"""
    text = json.dumps(gen.build_all(), ensure_ascii=False, indent=1) + "\n"
    assert text == (ROOT / "eval_bank_20260925" / "reasoning_20261012.json").read_text(encoding="utf-8")


def test_instances_are_scaled_up():
    sizes = {
        "NX-09": len(INSTANCES["NX-09"]["patients"]),
        "NX-10": len(INSTANCES["NX-10"]["vehicles"]),
        "NX-11": len(INSTANCES["NX-11"]["events"]),
        "NX-12": len(INSTANCES["NX-12"]["orders"]),
        "NX-13": len(INSTANCES["NX-13"]["flights"]),
        "NX-14": len(INSTANCES["NX-14"]["cars"]),
        "NX-15": len(INSTANCES["NX-15"]["patients"]),
        "NX-16": len(INSTANCES["NX-16"]["days"]),
        "NX-17": len(INSTANCES["NX-17"]["edges"]),
        "NX-18": len(INSTANCES["NX-18"]["orders"]),
    }
    assert sizes["NX-09"] >= 20 and sizes["NX-15"] >= 20 and sizes["NX-14"] >= 15 and sizes["NX-10"] >= 15
    assert sizes["NX-11"] >= 20 and sizes["NX-13"] >= 12 and sizes["NX-17"] >= 15
    assert sizes["NX-12"] == sizes["NX-18"] == 7 and sizes["NX-16"] == 10
    for i in IDS:
        assert len(render_reasoning_prompt(i)) < 1800, i


def test_empty_answer_baseline_is_zero():
    """全空/全零答案不得分（20261011 时为 21/200）。"""
    total = 0
    for i in IDS:
        blank = {}
        for name, value in reference_answer(i).items():
            blank[name] = [] if isinstance(value, list) else {} if isinstance(value, dict) else 0 if isinstance(value, int) else ""
        total += score_reasoning(i, json.dumps(blank))["points"]
    # NX-17 的 reason 在有解时为空字符串，空答案仍拿 2 分；其余为 0。权重本轮不调整。
    assert total == 2


# ---- 独立交叉验证（不调用 reasoning_gen 的求解器） ----

def _independent_route(inst, objective, unique=True):
    orders = inst["orders"]

    def road(a, b):
        if a == b:
            return 0
        return inst["roads"].get(f"{a}-{b}", inst["roads"].get(f"{b}-{a}"))

    results = []
    for route in itertools.permutations(sorted(orders)):
        t, pos, floor, walk, arr = 0, "W", 0, 0, []
        for oid in route:
            o = orders[oid]
            t += floor + road(pos, o["building"])
            t = max(t, o.get("ready", 0))
            stopped = any(a <= t < b for a, b in inst["outages"][o["building"]])
            climb = o["floor"] * (2 if stopped else 1)
            walk += climb if stopped else 0
            t += climb
            arr.append([oid, t])
            pos, floor = o["building"], o["floor"]
        late = sorted(oid for oid, x in arr if x > orders[oid]["deadline"])
        results.append((objective(late, t), list(route), arr, late, t, walk))
    results.sort(key=lambda r: r[0])
    if unique:
        assert results[0][0] < results[1][0], "optimum must be unique"
    return results[0]


def test_nx12_exhaustive_unique_optimum():
    _k, route, arr, late, total, _walk = _independent_route(INSTANCES["NX-12"], lambda late, t: t)
    assert reference_answer("NX-12") == {"route": route, "arrivals": arr, "late": late, "total": total}


def test_nx18_exhaustive_unique_optimum_and_late_first_objective():
    inst = INSTANCES["NX-18"]
    _k, route, arr, late, _t, walk = _independent_route(inst, lambda late, t: (len(late), t))
    assert reference_answer("NX-18") == {"route": route, "arrivals": arr, "late": late, "elevator_walk": walk}
    fastest = _independent_route(inst, lambda late, t: t, unique=False)
    assert fastest[0] < _t  # 只看完成时刻会得到更早但迟到更多的顺序


def test_nx16_brute_force_unique_optimum():
    inst = INSTANCES["NX-16"]
    days, cap, box = inst["days"], inst["capacity"], inst["box"]
    normal = [i for i, d in enumerate(days) if d["kind"] == "normal"]
    best, count, best_plan = None, 0, None
    for choice in itertools.product(range(0, cap + 1, box), repeat=len(normal)):
        buy = [0] * len(days)
        for i, b in zip(normal, choice):
            buy[i] = b
        old, profit, ok, sold_l, waste_l = 0, 0, True, [], []
        for i, d in enumerate(days):
            if old + buy[i] > cap:
                ok = False
                break
            s_old = min(old, d["demand"])
            s_new = min(buy[i], d["demand"] - s_old)
            waste = old - s_old
            carry = buy[i] - s_new
            if d["kind"] == "hot" or i == len(days) - 1:
                waste += carry
                carry = 0
            profit += (s_old + s_new) * d["price"] - buy[i] * d["cost"]
            sold_l.append(s_old + s_new)
            waste_l.append(waste)
            old = carry
        if not ok:
            continue
        if best is None or profit > best:
            best, count, best_plan = profit, 1, (buy, sold_l, waste_l)
        elif profit == best:
            count += 1
    assert count == 1
    assert reference_answer("NX-16") == {"buy": best_plan[0], "sold": best_plan[1], "waste": best_plan[2], "profit": best}


def test_nx17_exhaustive_paths_and_strict_best():
    inst = INSTANCES["NX-17"]
    graph = {}
    for u, v, m, c in inst["edges"]:
        graph.setdefault(u, []).append((v, m, c))
    found = []
    stack = [(inst["src"], [inst["src"]], 0, 0)]
    while stack:
        node, path, t, fee = stack.pop()
        if node == inst["dst"]:
            found.append((t, fee, path))
            continue
        for v, m, c in graph.get(node, []):
            if v in path or fee + c > inst["budget"]:
                continue
            if any(u == node and w == v and a <= t < b for u, w, a, b in inst["closures"]):
                continue
            stack.append((v, path + [v], t + m, fee + c))
    found.sort()
    assert found[0][:2] < found[1][:2]
    key = reference_answer("NX-17")
    assert [key["arrive"], key["cost"], key["path"]] == list(found[0])
    assert key["alternatives"] == [[p, t, c] for t, c, p in found[1:4]]
    assert key["reason"] == ""


def test_nx10_independent_per_vehicle_minimum_has_no_ties():
    inst = INSTANCES["NX-10"]

    def price(m):
        return next(p for a, b, p in inst["tariff"] if a <= m < b)

    busy = {k: [tuple(w) for w in v] for k, v in inst["reservations"].items()}
    assign, rejected = [], []
    for vid, arrive, energy, deadline in inst["vehicles"]:
        options = []
        for pile, power in inst["piles"].items():
            dur = math.ceil(energy / power)
            for s in range(arrive, deadline - dur + 1):
                if all(not (s < b and s + dur > a) for a, b in busy[pile]):
                    options.append((sum(price(m) for m in range(s, s + dur)), s + dur, pile, s))
        if not options:
            rejected.append(vid)
            continue
        options.sort()
        if len(options) > 1:
            assert options[0][:2] != options[1][:2]
        cost, end, pile, s = options[0]
        busy[pile].append((s, end))
        assign.append([vid, pile, s, end, cost])
    assert reference_answer("NX-10") == {"assign": assign, "rejected": rejected, "total_cost": sum(r[4] for r in assign)}


# ---- 泄露检查 ----

LEAK_PATTERNS = [
    "主动等待", "避开峰", "逐步", "一步步", "模拟", "提示", "注意", "陷阱", "难点", "技巧", "建议", "思路",
    "例如", "比如", "举例", "落地改为", "表示 F1", "先选已到达", "每当房间可用", "每当桩空闲", "每当床位可用",
    "按原计划优先保留", "已出发的边", "贪心", "动态规划", "穷举", "枚举", "回溯", "最短路", "Dijkstra",
    "按当天需求进货", "进满库容", "少卖",
]


@pytest.mark.parametrize("item_id", IDS)
def test_prompt_has_no_leaked_method_phrases(item_id):
    prompt = render_reasoning_prompt(item_id)
    hits = [p for p in LEAK_PATTERNS if p in prompt]
    assert not hits, hits


@pytest.mark.parametrize("item_id", IDS)
def test_prompt_does_not_contain_answer_values(item_id):
    prompt = render_reasoning_prompt(item_id)
    key = reference_answer(item_id)
    for name in ("route", "path"):
        if name in key:
            assert json.dumps(key[name], separators=(",", ":")) not in prompt
            assert "".join(key[name]) not in prompt
    assert json.dumps(key, ensure_ascii=False, separators=(",", ":")) not in prompt


def test_difficulty_notes_doc_never_reaches_prompts():
    doc = (ROOT / "docs" / "question-bank-reasoning-20261012.md").read_text(encoding="utf-8")
    notes = [m.strip() for m in re.findall(r"难点[：:](.+)", doc)]
    assert len(notes) == 10
    prompts = "\n".join(render_reasoning_prompt(i) for i in IDS)
    for note in notes:
        for fragment in re.split(r"[，。；、]", note):
            fragment = fragment.strip()
            if len(fragment) >= 8:
                assert fragment not in prompts, fragment


def test_every_output_field_is_defined_in_prompt():
    for i in IDS:
        prompt = render_reasoning_prompt(i)
        for name in reference_answer(i):
            assert f"- `{name}`：" in prompt, (i, name)


def test_seeds_are_derived_from_base_seed():
    for row in FROZEN["items"]:
        offset = int(row["item_id"].split("-")[1]) * 100000
        assert gen.BASE_SEED + offset <= row["seed"] < gen.BASE_SEED + offset + gen.MAX_TRIES
        inst = json.loads(json.dumps(gen.SPECS[row["item_id"]]["gen"](random.Random(row["seed"]))))
        assert inst == row["instance"]
