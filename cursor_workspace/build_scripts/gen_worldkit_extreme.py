#!/usr/bin/env python3
"""为外卖、出行、电梯各出一道极难，并统计题目数、因子数、相互作用系数。

相互作用沿用门禁的定义：单独拿掉甲、单独拿掉乙都会改变主指标，
同时拿掉的结果又和只拿掉甲、只拿掉乙都不同。系数 = 该因子如此相依的其他因子个数。

  .venv/bin/python -u cursor_workspace/build_scripts/gen_worldkit_extreme.py
"""
from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.worldkit import accel, answers, core, depth, render  # noqa: E402
from eval_bank_20260925.worldkit.families import delivery, elevator, trip  # noqa: E402
from eval_bank_20260925.worldkit.sample import load_config  # noqa: E402

WORLDS = ROOT / "eval_bank_20260925/worldkit/worlds"
OUT = ROOT / "out/worldkit"


def _mains(fam, solver, world) -> tuple:
    sol = solver(world)
    if sol.status != "ok":
        return ("无解",)
    return tuple(sol.best.metrics[q["metric"]] for q in core.main_questions(world))


def interaction(fam, world, solver=None) -> dict[str, list[str]]:
    """每个条件名 → 与它互相影响的其他条件名。"""
    solver = solver or core.Solver(fam)
    conds = core.conditions(fam, world)
    base = _mains(fam, solver, world)
    single = {c.name: _mains(fam, solver, c.apply(world)) for c in conds}
    out = {c.name: [] for c in conds}
    for a in conds:
        for b in conds:
            if a.name == b.name:
                continue
            ab = _mains(fam, solver, a.apply(b.apply(world)))
            if single[a.name] != base and single[b.name] != base and ab != single[a.name] and ab != single[b.name]:
                out[a.name].append(b.name)
    return out


def _questions(plan_text: str, metrics: list[tuple[str, str, int]], cf: tuple[str, str, int] | None) -> list[dict]:
    qs = [{"name": "plan", "type": "plan", "metric": metrics[0][0], "points": 6, "text": plan_text}]
    for name, metric, points in metrics:
        qs.append({"name": name, "metric": metric, "points": points})
    if cf:
        name, metric, points = cf
        qs.append({"name": name, "metric": metric, "points": points, "cf": "no_rain" if "dry" in name else "cap_plus_one"})
    return qs


def _trip_world(rng: random.Random) -> dict:
    names = ["家到路口", "路口到车站", "车站到园区门", "园区门到公司"]

    def leg(name: str) -> dict:
        def walk(lo, hi, lights=False):
            row = {"min": rng.randint(lo, hi)}
            if lights:
                row["lights"] = True
            return [row]

        return {
            "name": name,
            "walk": {"direct": walk(8, 14, True), "detour": walk(12, 18)},
            "bike": {"direct": walk(2, 4, True), "detour": walk(3, 6)},
            "bus": {
                "direct": {"access": rng.randint(1, 2), "ride": rng.randint(3, 6)},
                "detour": {"access": rng.randint(2, 4), "ride": rng.randint(5, 9)},
            },
        }

    step = rng.choice((6, 7, 8, 9))
    return {
        "family": "trip",
        "data": {
            "start": 0,
            "from_name": "家",
            "to_name": "公司",
            "legs": [leg(n) for n in names],
            "fare": {"walk": 0, "bike": 2, "bus": 3},
        },
        "modules": {
            "lights": {"cycle": 10, "green": 4},
            "rain": {},
            "bus_schedule": {"times": list(range(3, 100, step))},
            "transfer": {"minutes": rng.randint(4, 7)},
        },
        "objective": ["arrive", "fare"],
        "objective_conditions": {},
        "questions": [
            {"name": "plan", "type": "plan", "metric": "arrive", "points": 6,
             "text": "给出最优的各段选择。每段写成工具-路线，段与段也用短横线连接"
                     "（WALK/BIKE/BUS 与 DIRECT/DETOUR，如 WALK-DIRECT-BUS-DETOUR-WALK-DIRECT-BIKE-DETOUR）。"},
            {"name": "arrive", "metric": "arrive", "points": 5},
            {"name": "fare", "metric": "fare", "points": 4},
            {"name": "dry_arrive", "metric": "arrive", "points": 5, "cf": "no_rain"},
        ],
        "background": [],
    }


def _each_factor_moves(fam, world, metrics: tuple[str, ...]) -> bool:
    base_sol = core.solve(fam, world)
    base = tuple(base_sol.best.metrics[m] for m in metrics)
    for mid in world["modules"]:
        alt = copy.deepcopy(world)
        alt["modules"].pop(mid)
        sol = core.solve(fam, alt)
        if sol.status != "ok" or tuple(sol.best.metrics[m] for m in metrics) == base:
            return False
    return True


def hunt_trip() -> dict:
    hits = []
    for seed in range(5000, 5080):
        world = _trip_world(random.Random(seed))
        sol = core.solve(trip.FAMILY, world)
        if sol.status != "ok":
            continue
        tools = sol.best.plan[0::2]
        if "bus" not in tools or len(set(tools)) < 2:
            continue
        greedy = trip.greedy_leg_plan(world)
        gout = trip.FAMILY.simulate(world, greedy)
        if gout is None or gout.plan == sol.best.plan:
            continue
        if gout.metrics["arrive"] == sol.best.metrics["arrive"] or gout.metrics["fare"] == sol.best.metrics["fare"]:
            continue
        dry = copy.deepcopy(world)
        dry["modules"].pop("rain")
        dsol = core.solve(trip.FAMILY, dry)
        if dsol.status != "ok" or dsol.best.plan == sol.best.plan:
            continue
        if dsol.best.metrics["arrive"] == sol.best.metrics["arrive"]:
            continue
        if not _each_factor_moves(trip.FAMILY, world, ("arrive", "fare")):
            continue
        gap = abs(gout.metrics["arrive"] - sol.best.metrics["arrive"])
        hits.append((gap, seed, world))
        print(f"trip seed {seed} arrive_gap {gap} best {sol.best.plan} {sol.best.metrics} "
              f"greedy {gout.metrics}", flush=True)
        if len(hits) >= 4:
            break
    if not hits:
        raise SystemExit("trip: no extreme world")
    best = None
    for gap, seed, world in hits:
        nb = interaction(trip.FAMILY, world)
        degs = [len(v) for v in nb.values()]
        mean = sum(degs) / len(degs)
        print(f"trip seed {seed} degree_mean {mean:.2f}", flush=True)
        if best is None or (mean, gap) > best[0]:
            best = ((mean, gap), seed, world, nb)
    return {"world": best[2], "neighbors": best[3], "seed": best[1]}


def _elev_world() -> dict:
    """大厅 3 人、轿厢 2 人：先送最高层再立刻回大厅是可行的，但总等待和最长等待都更差。"""
    return {
        "family": "elevator",
        "data": {
            "floors": 6,
            "start_floor": 1,
            "start_time": 0,
            "speed": 1,
            "calls": [
                {"id": "P1", "from": 1, "to": 6, "at": 0},
                {"id": "P2", "from": 1, "to": 5, "at": 0},
                {"id": "P3", "from": 1, "to": 3, "at": 0},
                {"id": "P4", "from": 6, "to": 1, "at": 2},
                {"id": "P5", "from": 4, "to": 2, "at": 6},
            ],
            "stops": {"A": 1, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1},
        },
        "modules": {
            "cap": {"max": 2},
            "door": {"minutes": 2},
            "peak": {"floor": 4, "from_t": 11, "to_t": 24},
        },
        "objective": ["total_wait", "max_wait"],
        "objective_conditions": {},
        "questions": [
            {"name": "plan", "type": "plan", "metric": "total_wait", "points": 6,
             "text": "给出最优停靠点编号顺序，用短横线连接全部编号（如 A-B-C-D-E-F-G）。"},
            {"name": "total_wait", "metric": "total_wait", "points": 5},
            {"name": "max_wait", "metric": "max_wait", "points": 5},
            {"name": "cf_total_wait", "metric": "total_wait", "points": 4, "cf": "cap_plus_one"},
        ],
        "background": [],
    }


def hunt_elevator() -> dict:
    world = _elev_world()
    sol = core.solve(elevator.FAMILY, world)
    trap = elevator.high_then_return_plan(world)
    tout = elevator.FAMILY.simulate(world, trap)
    if sol.status != "ok" or tout is None or trap == sol.best.plan:
        raise SystemExit("elevator: trap collapsed")
    if tout.metrics["total_wait"] == sol.best.metrics["total_wait"] or tout.metrics["max_wait"] == sol.best.metrics["max_wait"]:
        raise SystemExit("elevator: trap shares a metric with the optimum")
    nb = interaction(elevator.FAMILY, world)
    print(f"elev feasible {sol.n_feasible} best {sol.best.plan} {sol.best.metrics} "
          f"trap {tout.metrics} neighbors { {k: len(v) for k, v in nb.items()} }", flush=True)
    return {"world": world, "neighbors": nb, "seed": 1}


def _solve_delivery(world: dict) -> dict:
    return accel.status(world, max_plans=400_000, seconds=50)


def _readings_move(world: dict, total: int, late_n: int) -> bool:
    base = (total, late_n)
    for fn in delivery.FAMILY.readings.values():
        alt = fn(world)
        if alt is None:
            continue
        st = _solve_delivery(alt)
        if st.get("status") != "ok" or (int(st["total"]), int(st["late_n"])) != base:
            return True
    return False


def _delivery_neighbors(world: dict) -> dict:
    """走 Go 门禁拿两两相依。删掉一条规则就会让后面的 oracle 停掉，避免再解一整遍。"""
    probe = copy.deepcopy(world)
    probe.setdefault("gates", {})["min_boundary"] = 99
    rep = accel.run_gates(probe, fail_fast=False, max_plans=400_000, seconds=180)
    block = rep.get("degree") or {}
    return block.get("neighbors") or {}


def hunt_delivery() -> dict:
    cfg = load_config("delivery")
    tier = cfg["tiers"]["极难"]
    found = None
    for seed in range(1400, 1448):
        world = delivery.sample(random.Random(seed), cfg, tier)
        st = _solve_delivery(world)
        if st.get("error") or st.get("status") != "ok":
            print(f"delivery seed {seed} {st.get('status') or st.get('error')}", flush=True)
            continue
        plan = depth.deadline_plan(world)
        out = delivery.FAMILY.simulate(delivery.FAMILY.effective(world), plan)
        if out is None:
            print(f"delivery seed {seed} greedy infeasible", flush=True)
            continue
        gap = abs(out.metrics["late_n"] - int(st["late_n"]))
        print(f"delivery seed {seed} late {st['late_n']}->{out.metrics['late_n']} "
              f"total {st['total']}->{out.metrics['total']}", flush=True)
        if gap < 2 or out.metrics["total"] == int(st["total"]):
            continue
        prepared = depth.prepare(copy.deepcopy(world), _solve_delivery)
        if prepared is None:
            print(f"delivery seed {seed} prepare failed", flush=True)
            continue
        st2 = _solve_delivery(prepared)
        if st2.get("error") or st2.get("status") != "ok":
            continue
        out2 = delivery.FAMILY.simulate(delivery.FAMILY.effective(prepared), depth.deadline_plan(prepared))
        if out2 is None or abs(out2.metrics["late_n"] - int(st2["late_n"])) < 2:
            print(f"delivery seed {seed} trap lost after prepare", flush=True)
            continue
        if out2.metrics["total"] == int(st2["total"]):
            continue
        report = depth.assess(prepared, {"depth": "late"}, _solve_delivery)
        # 冷链干扰筛会把「迟到差 2 单以上」的局几乎全部丢掉。极难只要蝴蝶效应和这条陷阱还在。
        if report["reason"] not in ("", "depth:distractor"):
            print(f"delivery seed {seed} {report['reason']}", flush=True)
            continue
        cf = _solve_delivery(delivery._swap_shock(prepared))
        if cf.get("status") != "ok" or int(cf["total"]) == int(st2["total"]):
            print(f"delivery seed {seed} cf not distinct", flush=True)
            continue
        if _readings_move(prepared, int(st2["total"]), int(st2["late_n"])):
            print(f"delivery seed {seed} readings", flush=True)
            continue
        print(f"delivery seed {seed} ACCEPT", flush=True)
        found = {"world": prepared, "seed": seed, "depth": report}
        break
    if found is None:
        raise SystemExit("delivery: no extreme world")
    print("delivery interaction", flush=True)
    found["neighbors"] = _delivery_neighbors(found["world"])
    print(f"delivery neighbors { {k: len(v) for k, v in found['neighbors'].items()} }", flush=True)
    return found


def _delivery_key(world: dict, base: dict, cf: dict) -> dict:
    key = {}
    for q in world["questions"]:
        src = cf if q.get("cf") else base
        key[q["name"]] = int(src[q["metric"]])
    return key


def _pack(fam, row: dict) -> dict:
    world = row["world"]
    solver = core.Solver(fam, core.Budget(400_000, 120))
    if fam.id == "delivery":
        st = _solve_delivery(world)
        best = fam.simulate(fam.effective(world), tuple(st["plan"]))
        cf = _solve_delivery(delivery._swap_shock(world))
        key = _delivery_key(world, st, cf)
    else:
        best = solver(world).best
        key = core.answers(fam, world, solver)
    prompt = render.render_prompt(fam, world)
    leaked = render.leaks(prompt)
    if leaked:
        raise SystemExit(f"{fam.id} leaks {leaked}")
    return {
        "id": f"{fam.id}-极难",
        "tier": "极难",
        "seed": row["seed"],
        "world": world,
        "answer": key,
        "prompt": prompt,
        "reference": answers.reference_text(world, key, solver, best=best),
        "neighbors": row["neighbors"],
    }


def _coef_lines(pack: dict) -> list[str]:
    nb = pack["neighbors"]
    world = pack["world"]
    n_q = len(world["questions"])
    n_f = len(world["modules"])
    bg = set(world.get("background") or [])
    degs = [len(v) for v in nb.values()]
    mean = sum(degs) / len(degs) if degs else 0
    lines = [f"{pack['id']}  题目 {n_q}  因子 {n_f}  平均相互作用系数 {mean:.2f}"]
    if bg:
        lines.append(f"  背景因子（不参与相依计数）: {', '.join(sorted(bg))}")
    for name, others in nb.items():
        lines.append(f"  {name}: {len(others)} → {', '.join(others) if others else '无'}")
    lines.append(f"  标准答案 {pack['reference']}")
    return lines


def main() -> int:
    print("hunt trip", flush=True)
    trip_row = hunt_trip()
    print("hunt elevator", flush=True)
    elev_row = hunt_elevator()
    print("hunt delivery", flush=True)
    del_row = hunt_delivery()
    packs = [
        _pack(delivery.FAMILY, del_row),
        _pack(trip.FAMILY, trip_row),
        _pack(elevator.FAMILY, elev_row),
    ]
    for fam_name, pack in (("delivery", packs[0]), ("trip", packs[1]), ("elevator", packs[2])):
        path = WORLDS / fam_name / "extreme.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pack["world"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extreme_candidates.json").write_text(
        json.dumps({"candidates": packs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(line for p in packs for line in _coef_lines(p)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
