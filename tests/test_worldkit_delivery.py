"""worldkit 配送题族：旧题复现、三方对拍、模块手算、变异检出、复核器隔离、题面泄漏、采样、判分。"""
from __future__ import annotations

import ast
import copy
import itertools
import json
from pathlib import Path

import pytest

from eval_bank_20260925 import reasoning_gen as rg
from eval_bank_20260925.worldkit import answers as ans
from eval_bank_20260925.worldkit import core, depth, gates, legacy, render, sample
from eval_bank_20260925.worldkit.families import delivery

ROOT = Path(__file__).resolve().parents[1]
FROZEN = {r["item_id"]: r for r in json.loads((ROOT / "eval_bank_20260925/reasoning_20261023.json").read_text())["items"]}
FAM = delivery.FAMILY


def nx_world(item_id: str) -> dict:
    return legacy.world_from_nx(item_id, FROZEN[item_id]["instance"])


# ---------------------------------------------------------------------------
# 旧题复现
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_reproduces_frozen_answer_and_route(item_id):
    w = nx_world(item_id)
    solver = core.Solver(FAM)
    assert core.answers(FAM, w, solver) == FROZEN[item_id]["answer"]
    assert list(solver(w).best.plan) == FROZEN[item_id]["full_answer"]["route"]


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_reproduces_frozen_deletion_and_degree(item_id):
    w = nx_world(item_id)
    solver = core.Solver(FAM)
    conds = core.conditions(FAM, w)
    rename = legacy.CONDITION_NAMES
    old_del = {rename.get(d["condition"], d["condition"]): set(d["changed"]) for d in FROZEN[item_id]["deletion"]}
    new_del = {d["condition"]: set(d["changed"]) for d in gates.deletion_report(w, solver, conds)}
    assert new_del == old_del
    old_deg = {rename.get(k, k): v for k, v in FROZEN[item_id]["degree"]["degree"].items()}
    assert gates.degree_report(w, solver, conds, 3)["degree"] == old_deg


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_engine_matches_independent_oracle(item_id):
    w = nx_world(item_id)
    solver = core.Solver(FAM)
    rep = gates.oracle_report(FAM, w, solver, core.conditions(FAM, w), core.answers(FAM, w, solver))
    assert rep["ok"], rep["mismatches"][:3]
    assert rep["variants"] == 29


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_engine_matches_legacy_solver_on_all_variants(item_id):
    """背景模块也参与消融：旧 `_deliver` 作第三方对照。"""
    w = dict(nx_world(item_id), background=[])
    conds = core.conditions(FAM, w)
    variants = [w] + [c.apply(w) for c in conds] + [a.apply(b.apply(w)) for a, b in itertools.combinations(conds, 2)]
    solver = core.Solver(FAM)
    bad = []
    for v in variants:
        mine = core.answers(FAM, v, solver)
        old = rg.key_answer(item_id, rg.solve(item_id, legacy.nx_from_world(v)))
        old = {k: (core.INFEASIBLE if isinstance(x, int) and x >= 10**5 else x) for k, x in old.items()}
        if mine != old:
            bad.append((sorted(v["modules"]), mine, old))
    assert not bad, bad[:3]


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_preset_files_match_frozen_instance(item_id):
    preset = json.loads((sample.WORLDS / "delivery/presets" / f"{item_id}.json").read_text(encoding="utf-8"))
    assert preset == dict(nx_world(item_id), gates={"min_degree": 3})


@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_frozen_items_pass_gates(item_id):
    rep = gates.run_gates(FAM, dict(nx_world(item_id), gates={"min_degree": 3}))
    assert rep["accept"], rep["reasons"]


# ---------------------------------------------------------------------------
# 模块手算（含历史 bug）
# 基准：W-L1 5、W-L2 8、L1-L2 4；A 在 L1 三楼，B 在 L2 二楼；顺序 A-B 时 A 8 分送达、B 14 分送达。
# ---------------------------------------------------------------------------

def tiny(**mods) -> dict:
    return {
        "family": "delivery",
        "data": {"roads": {"W-L1": 5, "W-L2": 8, "L1-L2": 4},
                 "orders": {"A": {"building": "L1", "floor": 3, "deadline": 99},
                            "B": {"building": "L2", "floor": 2, "deadline": 99},
                            "C": {"building": "L1", "floor": 1, "deadline": 99}},
                 "role": "骑手"},
        "modules": {"cancel": {"ids": ["C"]}, **mods},
        "objective": ["late_n", "total", "walk"],
        "objective_conditions": {},
        "questions": [{"name": "total", "metric": "total", "points": 20}],
        "background": [],
    }


def run(world: dict, plan: str):
    out = FAM.simulate(FAM.effective(world), tuple(plan.split("-")))
    return None if out is None else (dict(out.trace[0]), out.metrics, out.fired)


def test_canary_base():
    at, m, _ = run(tiny(), "A-B")
    assert at == {"A": 8, "B": 14} and m["late_n"] == 0 and m["walk"] == 0


def test_canary_down_and_congestion_counted_after_descending():
    assert run(tiny(down={"rate": 1}), "A-B")[0]["B"] == 17
    # 下楼后 11 分出发，已进入 10 分起的拥堵：路程 4 翻倍
    assert run(tiny(down={"rate": 1}, congestion={"from": 10, "mult": 2}), "A-B")[0]["B"] == 21
    assert run(tiny(congestion={"from": 10, "mult": 2}), "A-B")[0]["B"] == 14


def test_canary_register_only_on_first_visit():
    w = tiny(register={"minutes": {"L1": 2, "L2": 0}})
    w["modules"].pop("cancel")
    at, _, fired = run(w, "A-C-B")
    assert at["A"] == 10 and at["C"] == 11 and "register" in fired


def test_canary_closed_wait_and_boundary():
    assert run(tiny(closed={"spans": {"L1": [[4, 7]]}}), "A-B")[0]["A"] == 10
    out = FAM.simulate(FAM.effective(tiny(closed={"spans": {"L1": [[5, 9]]}})), ("A", "B"))
    assert dict(out.trace[0])["A"] == 12 and out.boundary == 1
    assert run(tiny(closed={"spans": {"L1": [[0, 5]]}}), "A-B")[0]["A"] == 8


def test_canary_ready_wait_then_outage_checked_at_climb_start():
    base = {"ready": {}, "outage": {"spans": {"L1": [[7, 20]], "L2": []}}}
    w = tiny(**copy.deepcopy(base))
    w["data"]["orders"]["A"]["ready"] = 9
    at, m, _ = run(w, "A-B")
    assert at["A"] == 9 + 6 and m["walk"] == 6
    w["modules"]["outage"]["check_at"] = "arrival"
    at, m, _ = run(w, "A-B")
    assert at["A"] == 12 and m["walk"] == 0


def test_canary_flood_deliver_vs_enter():
    assert run(tiny(flood={"t": 14, "building": "L2", "scope": "deliver"}), "A-B") is None
    assert run(tiny(flood={"t": 14, "building": "L2", "scope": "enter"}), "A-B")[0]["B"] == 14
    assert run(tiny(flood={"t": 12, "building": "L2", "scope": "enter"}), "A-B") is None


def test_canary_return_w_and_forced_carry_return():
    assert run(tiny(return_w={}), "A-W-B")[0]["B"] == 23
    at, _, fired = run(tiny(carry={"max": 1}), "A-B")
    assert at["B"] == 23 and "carry" in fired


def test_canary_cold_late_without_ready_module():
    _, m, fired = run(tiny(cold={"limit": 10}), "A-B")
    assert m["late_n"] == 1 and "cold" in fired


def test_canary_closed_spans_chain_in_either_order():
    for spans in ([[5, 9], [9, 14]], [[9, 14], [5, 9]]):
        assert run(tiny(closed={"spans": {"L1": spans}}), "A-B")[0]["A"] == 17


def test_canary_mutex_tie_breaks_by_building_name():
    w = tiny(closed={"spans": {"L2": [[6, 9]], "L1": [[6, 10]]}}, mutex={},
             flood={"t": 50, "building": "L1", "scope": "deliver"})
    assert list(FAM.effective(w)["modules"]["closed"]["spans"]) == ["L1"]
    from eval_bank_20260925.worldkit.oracles import delivery as oracle
    assert list(oracle._resolve_shocks(w["modules"])[0]["closed"]["spans"]) == ["L1"]


def test_canary_mutex_keeps_earliest_shock_flood_wins_tie():
    w = tiny(flood={"t": 6, "building": "L2", "scope": "deliver"}, closed={"spans": {"L1": [[6, 20]]}}, mutex={})
    live = FAM.effective(w)
    assert live["active_shock"] == "flood" and "closed" not in live["modules"]
    w["modules"]["closed"]["spans"]["L1"] = [[5, 20]]
    assert FAM.effective(w)["active_shock"] == "closed"


# ---------------------------------------------------------------------------
# 变异：植入的规则错误必须被复核器抓到
# ---------------------------------------------------------------------------

class _Mutant(delivery.DeliveryFamily):
    def __init__(self, mutate):
        self._mutate = mutate

    def simulate(self, world, plan):
        return super().simulate(self._mutate(world), plan)


def _drop(mid):
    def fn(w):
        x = copy.deepcopy(w)
        x["modules"].pop(mid, None)
        return x
    return fn


def _flood_enter(w):
    x = copy.deepcopy(w)
    if "flood" in x["modules"]:
        x["modules"]["flood"]["scope"] = "enter"
    return x


@pytest.mark.parametrize("item_id,mutate", [("NX-12", _drop("register")), ("NX-12", _drop("down")),
                                            ("NX-18", _drop("cold")), ("NX-18", _flood_enter)])
def test_oracle_catches_planted_bug(item_id, mutate):
    fam = _Mutant(mutate)
    w = nx_world(item_id)
    solver = core.Solver(fam)
    rep = gates.oracle_report(fam, w, solver, core.conditions(fam, w), core.answers(fam, w, solver))
    assert not rep["ok"]


def test_oracle_does_not_import_engine_or_family():
    for path in (ROOT / "eval_bank_20260925/worldkit/oracles").glob("*.py"):
        if path.name == "__init__.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for n in names:
                assert "worldkit" not in n and "reasoning" not in n, f"{path.name} imports {n}"


# ---------------------------------------------------------------------------
# 题面
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("item_id", ["NX-12", "NX-18"])
def test_prompt_has_no_internal_leaks(item_id):
    w = nx_world(item_id)
    prompt = render.render_prompt(FAM, w)
    assert render.leaks(prompt) == []
    assert "支持" not in prompt
    assert prompt.count("问") >= len(w["questions"])


# ---------------------------------------------------------------------------
# 采样
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tier", ["简单", "中等"])
def test_sampler_produces_accepted_item_with_histogram(tier):
    cfg = sample.load_config("delivery")
    out = sample.generate(cfg, tier, delivery.sample, delivery.perturbations, want=1, seed0=1000, max_tries=60)
    assert len(out["items"]) == 1
    item = out["items"][0]
    assert item["gates"]["accept"] and item["gates"]["oracle"]["ok"]
    assert isinstance(out["rejections"], dict) and out["tries"] >= 1
    assert render.leaks(render.render_prompt(FAM, item["world"])) == []


def test_sampler_is_deterministic():
    cfg = sample.load_config("delivery")
    tier = cfg["tiers"]["中等"]
    import random
    assert delivery.sample(random.Random(7), cfg, tier) == delivery.sample(random.Random(7), cfg, tier)


def test_twin_search_changes_one_parameter():
    w = tiny(flood={"t": 13, "building": "L2", "scope": "deliver"})
    w["objective"] = ["total"]
    variants = delivery.perturbations(w)
    assert variants and all(desc for desc, _ in variants)
    for _, alt in variants:
        diff = [k for k in alt["modules"] if alt["modules"][k] != w["modules"][k]]
        assert len(diff) == 1


# ---------------------------------------------------------------------------
# 判分：四种答案类型
# ---------------------------------------------------------------------------

def _scored_world(**over):
    w = tiny(**over)
    w["questions"] = [{"name": "plan", "type": "plan", "metric": "total", "points": 8},
                      {"name": "total", "metric": "total", "points": 6},
                      {"name": "late_n", "metric": "late_n", "points": 6}]
    return w


def _score(w, text):
    solver = core.Solver(FAM)
    return ans.score(FAM, w, core.answers(FAM, w, solver), text, solver)


def test_score_exact_and_plan_full_marks():
    w = _scored_world()
    assert core.answers(FAM, w) == {"plan": 14, "total": 14, "late_n": 0}
    r = _score(w, "推理……\nANSWER: A-B; 14; 0")
    assert r["passed"] and r["points"] == 20 and r["score10"] == 10.0


def test_score_plan_accepts_any_optimal_rejects_suboptimal_and_bad_orders():
    w = _scored_world()
    assert _score(w, "ANSWER: B-A; 14; 0")["groups"][0]["points"] == 0  # B-A：8+2+4+3=17，非最优
    assert _score(w, "ANSWER: A; 14; 0")["groups"][0]["why"] == "plan_orders_mismatch"
    assert _score(w, "ANSWER: A-W-B; 14; 0")["groups"][0]["why"] == "plan_return_not_allowed"
    assert _score(w, "ANSWER: A-C-B; 14; 0")["groups"][0]["why"] == "plan_orders_mismatch"


def test_score_plan_forced_carry_return_written_as_w_is_same_plan():
    w = _scored_world(carry={"max": 1})
    assert _score(w, "ANSWER: A-W-B; 23; 0")["passed"]


def test_score_plan_infeasible_route_scores_zero():
    w = _scored_world(flood={"t": 12, "building": "L2", "scope": "deliver"})
    assert core.answers(FAM, w)["total"] == 17  # 只能先送 B
    r = _score(w, "ANSWER: A-B; 17; 0")
    assert r["groups"][0]["why"] == "plan_infeasible" and r["points"] == 12


def test_score_tolerance_bounds():
    w = _scored_world()
    w["questions"][1] = {"name": "total", "type": "tolerance", "metric": "total", "points": 6,
                         "accept": {"lo": {"delta": -1}, "hi": {"delta": 2}}}
    pts = [_score(w, f"ANSWER: A-B; {v}; 0")["groups"][1]["points"] for v in (12, 13, 16, 17)]
    assert pts == [0, 6, 6, 0]


def test_score_threshold_plan():
    w = _scored_world()
    w["questions"][0]["accept"] = {"metric": "total", "max": {"delta": 3}}
    assert _score(w, "ANSWER: B-A; 14; 0")["groups"][0]["points"] == 8
    w["questions"][0]["accept"] = {"metric": "total", "max": 16}
    assert _score(w, "ANSWER: B-A; 14; 0")["groups"][0]["points"] == 0


def test_score_infeasible_items():
    w = _scored_world(flood={"t": 9, "building": "L2", "scope": "deliver"})
    w["modules"].pop("cancel")
    w["data"]["orders"]["C"]["building"] = "L2"
    assert core.answers(FAM, w)["total"] == core.INFEASIBLE
    assert _score(w, "ANSWER: 无解")["points"] == 20
    assert _score(w, "ANSWER: 无解; 无解; 无解")["points"] == 20
    assert _score(w, "ANSWER: A-B-C; 无解; 无解")["points"] == 12
    # 可解题答无解不得分
    assert _score(_scored_world(), "ANSWER: 无解")["points"] == 0


def test_score_accepts_arrows_commas_and_units():
    w = _scored_world()
    assert _score(w, "ANSWER: A->B; 14分钟; 第0")["passed"]
    assert _score(w, "ANSWER: A, B; 14; 0")["passed"]
    assert _score(w, "ANSWER: A-B; 14（不是无解）; 0")["passed"]


def test_conflict_core_keeps_nonrelaxing_modules():
    """取消订单的消融会加回订单，不能拿来证明冲突核（困难-无解 seed 172 是反例）。"""
    cfg = sample.load_config("delivery")
    # 梯度上移后，这个反例固定在当初的 5 单档，不跟当前「困难-无解」走。
    tier = {"orders": 5, "buildings": 3,
            "modules": ["outage", "register", "down", "congestion", "cancel", "closed", "carry", "ready", "flood", "mutex"],
            "objective": ["late_n", "total", "walk"], "objective_conditions": {"late_n": "先少迟到"},
            "cf": True, "infeasible": True, "gates": {"min_degree": 3, "min_boundary": 1}, "max_plans": 50000}
    w = delivery.sample(__import__("random").Random(172), cfg, tier)
    solver = core.Solver(FAM, sample._budget(tier))
    assert solver(w).status == "infeasible"
    rep = gates.conflict_report(w, solver, core.conditions(FAM, w))
    assert not rep["ok"]


def test_score_format_errors():
    w = _scored_world()
    assert _score(w, "答案是 14")["reason_code"] == "format_error"
    assert _score(w, "ANSWER: A-B; 14")["reason_code"] == "format_error"
    assert _score(w, "ANSWER: A-B; 14 或 15; 0")["groups"][1]["why"] == "not_single_integer"


def test_reference_text_round_trips():
    w = _scored_world()
    solver = core.Solver(FAM)
    key = core.answers(FAM, w, solver)
    assert ans.score(FAM, w, key, ans.reference_text(w, key, solver), solver)["passed"]


def test_header_states_direct_travel():
    cfg = sample.load_config("delivery")
    w = delivery.sample(__import__("random").Random(1), cfg, cfg["tiers"]["简单"])
    text = FAM.header(w)
    assert "一次直达的行驶分钟" in text
    assert "不经其他地点" in text


def test_deadline_plan_returns_between_full_groups():
    world = {"modules": {"carry": {"max": 2}},
             "data": {"orders": {"A": {"deadline": 5}, "B": {"deadline": 9}, "C": {"deadline": 1}}}}
    assert depth.deadline_plan(world) == ("C", "A", "W", "B")


def _depth_world():
    return {
        "family": "delivery",
        "data": {"orders": {
            "A": {"building": "L1", "floor": 1, "deadline": 10, "ready": 0},
            "B": {"building": "L1", "floor": 1, "deadline": 30, "ready": 0},
        }, "roads": {"W-L1": 2}},
        "modules": {
            "ready": {}, "down": {"rate": 1}, "carry": {"max": 2}, "return_w": {},
            "congestion": {"from": 5, "mult": 2}, "cold": {"limit": 40},
            "flood": {"t": 50, "building": "L1", "scope": "deliver"},
            "closed": {"spans": {"L1": [[1, 3]]}}, "mutex": {},
            "outage": {"spans": {"L1": [[1, 2]]}}, "register": {"minutes": {"L1": 0}},
        },
        "objective": ["late_n", "total", "walk"],
        "objective_conditions": {"late_n": "先少迟到"},
        "questions": [], "background": ["flood", "cold"], "gates": {},
    }


def test_depth_order_accepts_same_late_trap():
    world = _depth_world()
    base = {"status": "ok", "plan": ["A", "B"], "late": [], "late_n": 0, "total": 10,
            "fired": ["ready", "down"], "arrivals": {"A": 4, "B": 8}}

    def solve(w):
        if "congestion" not in w["modules"]:
            return {**base, "plan": ["B", "A"]}
        if "cold" not in w["modules"]:
            return base
        if w["modules"]["cold"]["limit"] < 40:
            return {**base, "plan": ["B", "A"], "late": ["A"], "late_n": 1}
        if w["modules"]["flood"]["t"] != 50:
            return {**base, "plan": ["B", "A"], "fired": ["ready", "down", "closed"]}
        return base

    report = depth.assess(world, {"depth": "order"}, solve)
    assert report["ok"], report
    assert report["trap"] == "无视拥堵阈值"
    assert report["distractor"]
    late = depth.assess(world, {"depth": "late"}, solve)
    assert not late["ok"] and late["reason"] == "depth:trap"
