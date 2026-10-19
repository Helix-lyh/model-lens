#!/usr/bin/env python3
"""生成 10 道极难：贪心答案只拿到 4/20，约 20%。

  .venv/bin/python -u cursor_workspace/build_scripts/gen_worldkit_extreme10.py
"""
from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.worldkit import accel, answers, core, render  # noqa: E402
from eval_bank_20260925.worldkit import extreme_screen as scr  # noqa: E402
from eval_bank_20260925.worldkit.families import delivery, elevator, trip  # noqa: E402
from eval_bank_20260925.worldkit.sample import load_config  # noqa: E402

OUT = ROOT / "out/worldkit"
BANK = ROOT / "eval_bank_20260925/worldkit/worlds/extreme10"


def _status(world: dict) -> dict:
    return accel.status(world, max_plans=400_000, seconds=40)


def _readings_move(world: dict, total: int, late_n: int) -> bool:
    base = (total, late_n)
    for fn in delivery.FAMILY.readings.values():
        alt = fn(world)
        if alt is None:
            continue
        st = _status(alt)
        if st.get("status") != "ok" or (int(st["total"]), int(st["late_n"])) != base:
            return True
    return False


def _delivery_tier() -> dict:
    tier = copy.deepcopy(load_config("delivery")["tiers"]["极难"])
    tier["orders"] = 8
    tier["modules"] = [m for m in tier["modules"] if m not in ("return_w", "cold")]
    tier["gates"] = {"min_degree": 0, "min_boundary": 0}
    tier.pop("depth", None)
    return tier


def _best_py(world: dict, st: dict):
    plan = tuple(st["plan"])
    out = delivery.FAMILY.simulate(delivery.FAMILY.effective(world), plan)
    if out is None:
        return None
    if out.metrics["total"] != int(st["total"]) or out.metrics["late_n"] != int(st["late_n"]):
        return None
    return {
        "plan": plan,
        "late": sorted(scr.late_ids(out)),
        "late_n": out.metrics["late_n"],
        "total": out.metrics["total"],
        "out": out,
    }


def hunt_delivery(want: int, seed0: int) -> list[dict]:
    cfg = load_config("delivery")
    tier = _delivery_tier()
    found = []
    for seed in range(seed0, seed0 + 500):
        if len(found) >= want:
            break
        world = delivery.sample(random.Random(seed), cfg, tier)
        if not scr.repair_windows(world, random.Random(seed)):
            print(f"delivery {seed} window", flush=True)
            continue
        forced = scr.solo_late_orders(world)
        if forced:
            print(f"delivery {seed} forced {forced}", flush=True)
            continue
        st = _status(world)
        if st.get("error") or st.get("status") != "ok":
            print(f"delivery {seed} {st.get('status') or st.get('error')}", flush=True)
            continue
        best = _best_py(world, st)
        if best is None:
            print(f"delivery {seed} py/go mismatch", flush=True)
            continue
        trap = scr.trap_row(world, best)
        if trap is None:
            print(f"delivery {seed} no 20% trap late {best['late_n']} total {best['total']}", flush=True)
            continue
        cf_world = delivery._swap_shock(world)
        cf = _status(cf_world)
        if cf.get("status") != "ok" or int(cf["total"]) == best["total"]:
            print(f"delivery {seed} cf collapsed", flush=True)
            continue
        replay = delivery.FAMILY.simulate(delivery.FAMILY.effective(cf_world), trap["plan"])
        wrong_cf = best["total"]
        if replay is not None and replay.metrics["total"] != int(cf["total"]):
            wrong_cf = replay.metrics["total"]
        if wrong_cf == int(cf["total"]):
            wrong_cf = int(cf["total"]) + 7
        if _readings_move(world, best["total"], best["late_n"]):
            print(f"delivery {seed} readings", flush=True)
            continue
        key = {
            "plan": best["total"],
            "total": best["total"],
            "late_n": best["late_n"],
            "cf_total": int(cf["total"]),
        }
        text = f"ANSWER: {'-'.join(trap['plan'])}; {trap['total']}; {trap['late_n']}; {wrong_cf}"
        scored = answers.score(delivery.FAMILY, world, key, text, best=best["out"])
        if scored["points"] != 4:
            print(f"delivery {seed} trap scores {scored['points']} not 4", flush=True)
            continue
        prompt = render.render_prompt(delivery.FAMILY, world)
        if render.leaks(prompt):
            print(f"delivery {seed} leak", flush=True)
            continue
        row = {
            "id": f"delivery-极难-{seed}",
            "tier": "极难",
            "seed": seed,
            "scene": "外卖",
            "world": world,
            "answer": key,
            "prompt": prompt,
            "reference": answers.reference_text(world, key, core.Solver(delivery.FAMILY), best=best["out"]),
            "trap": trap["name"],
            "trap_answer": text,
            "trap_points": scored["points"],
        }
        found.append(row)
        print(f"delivery {seed} KEEP trap={trap['name']} {scored['points']}/20 ref {row['reference']}", flush=True)
    return found


def _trip_world(rng: random.Random, n_legs: int) -> dict:
    names = ["家到路口", "路口到车站", "车站到园区门", "园区门到公司", "公司到会议室"][:n_legs]

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

    step = rng.choice((7, 8, 9))
    example = "-".join(["WALK-DIRECT", "BUS-DETOUR"] * (n_legs // 2) + (["BIKE-DIRECT"] if n_legs % 2 else []))
    return {
        "family": "trip",
        "data": {
            "start": 0,
            "from_name": "家",
            "to_name": "公司" if n_legs < 5 else "会议室",
            "legs": [leg(n) for n in names],
            "fare": {"walk": 0, "bike": 2, "bus": 3},
        },
        "modules": {
            "lights": {"cycle": 10, "green": 4},
            "rain": {},
            "bus_schedule": {"times": list(range(3, 120, step))},
            "transfer": {"minutes": rng.randint(4, 7)},
        },
        "objective": ["arrive", "fare"],
        "objective_conditions": {},
        "questions": [
            {"name": "plan", "type": "plan", "metric": "arrive", "points": 6,
             "text": "给出最优的各段选择。每段写成工具-路线，段与段也用短横线连接"
                     f"（WALK/BIKE/BUS 与 DIRECT/DETOUR，如 {example}）。"},
            {"name": "arrive", "metric": "arrive", "points": 5},
            {"name": "fare", "metric": "fare", "points": 4},
            {"name": "dry_arrive", "metric": "arrive", "points": 5, "cf": "no_rain"},
        ],
        "background": [],
    }


def hunt_trip(want: int, seed0: int) -> list[dict]:
    found = []
    for seed in range(seed0, seed0 + 200):
        if len(found) >= want:
            break
        world = _trip_world(random.Random(seed), 5)
        sol = core.solve(trip.FAMILY, world)
        if sol.status != "ok":
            continue
        greedy = trip.greedy_leg_plan(world)
        gout = trip.FAMILY.simulate(world, greedy)
        if gout is None or gout.plan == sol.best.plan:
            continue
        if gout.metrics["fare"] != sol.best.metrics["fare"] or gout.metrics["arrive"] == sol.best.metrics["arrive"]:
            continue
        dry = copy.deepcopy(world)
        dry["modules"].pop("rain")
        dsol = core.solve(trip.FAMILY, dry)
        if dsol.status != "ok" or dsol.best.metrics["arrive"] == sol.best.metrics["arrive"]:
            continue
        key = {
            "plan": sol.best.metrics["arrive"],
            "arrive": sol.best.metrics["arrive"],
            "fare": sol.best.metrics["fare"],
            "dry_arrive": dsol.best.metrics["arrive"],
        }
        dry_wrong = gout.metrics["arrive"]
        if dry_wrong == key["dry_arrive"]:
            dry_wrong = gout.metrics["arrive"] + 3
        text = "ANSWER: " + "-".join(x.upper() for x in gout.plan) + f"; {gout.metrics['arrive']}; {gout.metrics['fare']}; {dry_wrong}"
        scored = answers.score(trip.FAMILY, world, key, text, best=sol.best)
        if scored["points"] != 4:
            continue
        prompt = render.render_prompt(trip.FAMILY, world)
        if render.leaks(prompt):
            continue
        found.append({
            "id": f"trip-极难-{seed}",
            "tier": "极难",
            "seed": seed,
            "scene": "出行",
            "world": world,
            "answer": key,
            "prompt": prompt,
            "reference": answers.reference_text(world, key, core.Solver(trip.FAMILY), best=sol.best),
            "trap": "每段按表上最短分钟",
            "trap_answer": text,
            "trap_points": 4,
        })
        print(f"trip {seed} KEEP ref {found[-1]['reference']}", flush=True)
    return found


def _elev_world(rng: random.Random) -> dict:
    stops = {"A": 1, "B": 6, "C": 5, "D": 4, "E": 3, "F": 2, "G": 1}
    calls = [
        {"id": "P1", "from": 1, "to": 6, "at": 0},
        {"id": "P2", "from": 1, "to": 5, "at": 0},
        {"id": "P3", "from": 1, "to": 3, "at": 0},
        {"id": "P4", "from": 6, "to": 1, "at": rng.choice((1, 2, 3, 4))},
        {"id": "P5", "from": 4, "to": 2, "at": rng.choice((4, 6, 8, 10))},
    ]
    lo = rng.randint(6, 20)
    return {
        "family": "elevator",
        "data": {
            "floors": 6, "start_floor": 1, "start_time": 0, "speed": 1,
            "calls": calls, "stops": stops,
        },
        "modules": {
            "cap": {"max": 2},
            "door": {"minutes": rng.choice((1, 2))},
            "peak": {"floor": rng.choice((3, 4, 5)), "from_t": lo, "to_t": lo + rng.randint(8, 16)},
        },
        "objective": ["total_wait", "max_wait"],
        "objective_conditions": {},
        "questions": [
            {"name": "plan", "type": "plan", "metric": "total_wait", "points": 4,
             "text": "给出最优停靠点编号顺序，用短横线连接全部编号。"},
            {"name": "total_wait", "metric": "total_wait", "points": 6},
            {"name": "max_wait", "metric": "max_wait", "points": 5},
            {"name": "cf_total_wait", "metric": "total_wait", "points": 5, "cf": "cap_plus_one"},
        ],
        "background": [],
    }


def hunt_elevator(want: int, seed0: int) -> list[dict]:
    found = []
    for seed in range(seed0, seed0 + 80):
        if len(found) >= want:
            break
        world = _elev_world(random.Random(seed))
        sol = core.solve(elevator.FAMILY, world)
        if sol.status != "ok" or sol.n_feasible < 20:
            continue
        trap = elevator.high_then_return_plan(world)
        tout = elevator.FAMILY.simulate(world, trap)
        if tout is None or trap == sol.best.plan:
            continue
        if tout.metrics["total_wait"] == sol.best.metrics["total_wait"] and tout.metrics["max_wait"] == sol.best.metrics["max_wait"]:
            continue
        cf = core.solve(elevator.FAMILY, elevator._cap_plus_one(world))
        if cf.status != "ok" or cf.best.metrics["total_wait"] == sol.best.metrics["total_wait"]:
            continue
        key = {
            "plan": sol.best.metrics["total_wait"],
            "total_wait": sol.best.metrics["total_wait"],
            "max_wait": sol.best.metrics["max_wait"],
            "cf_total_wait": cf.best.metrics["total_wait"],
        }
        wrong_total = tout.metrics["total_wait"] if tout.metrics["total_wait"] != key["total_wait"] else key["total_wait"] + 9
        wrong_max = tout.metrics["max_wait"] if tout.metrics["max_wait"] != key["max_wait"] else key["max_wait"] + 3
        wrong_cf = tout.metrics["total_wait"] if tout.metrics["total_wait"] != key["cf_total_wait"] else key["cf_total_wait"] + 5
        text = f"ANSWER: {'-'.join(trap)}; {wrong_total}; {wrong_max}; {wrong_cf}"
        scored = answers.score(elevator.FAMILY, world, key, text, best=sol.best)
        if scored["points"] != 0:
            continue
        prompt = render.render_prompt(elevator.FAMILY, world)
        if render.leaks(prompt):
            continue
        found.append({
            "id": f"elevator-极难-{seed}",
            "tier": "极难",
            "seed": seed,
            "scene": "电梯",
            "world": world,
            "answer": key,
            "prompt": prompt,
            "reference": answers.reference_text(world, key, core.Solver(elevator.FAMILY), best=sol.best),
            "trap": "先去最高层再立刻回大厅",
            "trap_answer": text,
            "trap_points": scored["points"],
        })
        print(f"elev {seed} KEEP feas {sol.n_feasible} ref {found[-1]['reference']}", flush=True)
    return found


def main() -> int:
    print("hunt elevator", flush=True)
    rows = hunt_elevator(4, 7100)
    print("hunt trip", flush=True)
    rows += hunt_trip(2, 8200)
    print("hunt delivery", flush=True)
    rows += hunt_delivery(4, 3000)
    if len(rows) < 10:
        print("top up elevator", flush=True)
        rows += hunt_elevator(10 - len(rows), 7300)
    if len(rows) < 10:
        print(f"only {len(rows)} items", flush=True)
        return 1
    BANK.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (BANK / f"{row['id']}.json").write_text(
            json.dumps(row["world"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extreme10_candidates.json").write_text(
        json.dumps({"candidates": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"WROTE {len(rows)}", flush=True)
    for row in rows:
        print(f"{row['scene']}\t{row['id']}\ttrap {row['trap_points']}/20\t{row['reference']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
