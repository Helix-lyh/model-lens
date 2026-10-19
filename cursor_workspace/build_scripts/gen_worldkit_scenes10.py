#!/usr/bin/env python3
"""为七个新场景各冻结一道极难题：显眼贪心答对 4 分那一问，方案、主值和反事实都错。"""
from __future__ import annotations

import copy
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.worldkit import answers, core, render  # noqa: E402
from eval_bank_20260925.worldkit.families import charge, deice, gate, kitchen, line, signal, ward  # noqa: E402

OUT = ROOT / "eval_bank_20260925/worldkit/worlds/scenes10"
OLD = ROOT / "eval_bank_20260925/worldkit/worlds/extreme10"


def _world(fam, data, modules, objective) -> dict:
    return {
        "family": fam.id,
        "data": data,
        "modules": modules,
        "objective": objective,
        "questions": fam.questions(),
        "background": [],
    }


def _trap(fam, world: dict, min_gap: int, *, bite: str | None = None, salient=None, max_opt: int = 10**9):
    sol = core.solve(fam, world)
    if sol.status != "ok" or len(sol.optimal) > max_opt:
        return None
    if bite:
        bare = copy.deepcopy(world)
        bare["modules"].pop(bite, None)
        bsol = core.solve(fam, bare)
        if bsol.status != "ok" or bsol.best.metrics[fam.primary] == sol.best.metrics[fam.primary]:
            return None
    key = core.answers(fam, world)
    cf_world = fam.counterfactuals[fam.cf_key].transform(world)
    cf_sol = core.solve(fam, cf_world)
    if cf_sol.status != "ok":
        return None
    if cf_sol.best.metrics[fam.primary] == sol.best.metrics[fam.primary]:
        return None
    plans = [salient(world)] if salient else fam.greedies(world)
    for gplan in plans:
        if not gplan:
            continue
        gout = fam.simulate(world, gplan)
        if gout is None:
            continue
        if core.objective_key(world, gout) == core.objective_key(world, sol.best):
            continue
        if gout.metrics[fam.shared] != sol.best.metrics[fam.shared]:
            continue
        if gout.metrics[fam.primary] < sol.best.metrics[fam.primary] + min_gap:
            continue
        gcf = fam.simulate(cf_world, gplan)
        if gcf is None or gcf.metrics[fam.primary] == cf_sol.best.metrics[fam.primary]:
            continue
        parts = []
        for q in world["questions"]:
            if q.get("type") == "plan":
                parts.append("-".join(gplan))
            elif q.get("cf"):
                parts.append(str(gcf.metrics[fam.primary]))
            else:
                parts.append(str(gout.metrics[q["metric"]]))
        text = "ANSWER: " + "; ".join(parts)
        scored = answers.score(fam, world, key, text, best=sol.best)
        if scored["points"] != 4:
            continue
        if render.leaks(render.render_prompt(fam, world)):
            continue
        ref = answers.score(fam, world, key, answers.reference_text(world, key, core.Solver(fam), best=sol.best), best=sol.best)
        if not ref["passed"]:
            continue
        return {"plan": list(gplan), "points": 4, "n_opt": len(sol.optimal),
                "optimal": dict(sol.best.metrics), "greedy": dict(gout.metrics)}
    return None


def sample_signal(rng: random.Random) -> dict:
    phases = ["NS", "EW", "NL", "EL", "PD"]
    vehicles = []
    for phase in phases:
        vehicles.append({"phase": phase, "at": rng.choice([0, 6, 12]), "n": rng.randint(2, 4)})
        if phase != "PD" and rng.random() < 0.85:
            vehicles.append({"phase": phase, "at": rng.choice([20, 28, 36, 44]), "n": rng.choice([1, 2])})
    lo = rng.choice([4, 8, 14])
    return _world(signal.FAMILY, {
        "phases": phases,
        "greens": {"S": 12, "M": 22, "L": 34},
        "lost": 3,
        "headway": 3,
        "miss": 70,
        "vehicles": vehicles,
    }, {
        "ped": {"phase": "PD", "min": 34},
        "offset": {"lo": lo, "hi": lo + rng.choice([18, 26, 34])},
        "rain": {"extra": 1},
    }, ["delay", "max_delay"])


def sample_deice(rng: random.Random) -> dict:
    planes = []
    kinds = ["P", "P", "P", "P", "Q", "Q", "Q", "Q"]
    rng.shuffle(kinds)
    for name, kind in zip("ABCDEFGH", kinds):
        ready = rng.randint(0, 6)
        spray = rng.randint(6, 12)
        slot = ready + spray + rng.randint(0, 6)
        planes.append({"id": name, "ready": ready, "slot": slot, "deice": spray, "hold": 2, "kind": kind})
    return _world(deice.FAMILY, {"planes": planes}, {
        "sep": {"minutes": 3},
        "flush": {"minutes": 12},
        "fluid": {"bonus": 8},
    }, ["delay", "redeice"])


def sample_line(rng: random.Random) -> dict:
    families = ["W", "X", "Y", "Z"]
    assign = [families[i % 4] for i in range(8)]
    rng.shuffle(assign)
    jobs = []
    for name, fam in zip("ABCDEFGH", assign):
        jobs.append({"id": name, "family": fam, "minutes": rng.randint(5, 11), "due": rng.randint(24, 55)})
    keys = ["IDLE", *families]
    setup = {a: {} for a in keys}
    for a in keys:
        for b in families:
            setup[a][b] = 0 if a == b else rng.randint(3, 11)
    pair = [rng.choice(families)]
    pair.append(rng.choice([f for f in families if f != pair[0]]))
    return _world(line.FAMILY, {"jobs": jobs, "setup": setup}, {"fixture": {"pair": pair}}, ["tardiness", "changes"])


def sample_kitchen(rng: random.Random) -> dict:
    dishes = []
    pans = ["炒", "炒", "炒", "炒", "炖", "炖", "炖", "炖"]
    rng.shuffle(pans)
    for i, name in enumerate("ABCDEFGH"):
        table = f"T{i // 2 + 1}"
        long = i % 2 == 0
        dishes.append({
            "id": name,
            "table": table,
            "cook": rng.randint(8, 14) if long else rng.randint(3, 6),
            "hold": 70,
            "pan": pans[i],
        })
    return _world(kitchen.FAMILY, {"dishes": dishes}, {
        "rush": {"ids": [d["id"] for d in dishes if d["cook"] >= 8][:3], "extra": 4},
        "pan": {"minutes": 15},
    }, ["flow", "spoils"])


def sample_charge(rng: random.Random) -> dict:
    cars = [{"id": name, "need": rng.randint(4, 8), "depart": rng.randint(8, 28)} for name in "ABCDEFGH"]
    return _world(charge.FAMILY, {"cars": cars}, {
        "share": {},
        "block": {"lo": 0, "hi": rng.choice([8, 12, 16])},
        "topup": {"extra": 3},
    }, ["late", "late_n"])


def sample_ward(rng: random.Random) -> dict:
    patients = []
    grades = ["甲", "甲", "甲", "甲", "乙", "乙", "乙", "乙"]
    rng.shuffle(grades)
    for i, name in enumerate("ABCDEFGH"):
        patients.append({
            "id": name,
            "arrive": i * 2,
            "limit": rng.randint(1, 4),
            "stay": rng.randint(6, 12),
            "iso": i < 4,
            "grade": grades[i],
        })
    at = rng.choice([4, 6, 8])
    return _world(ward.FAMILY, {"patients": patients}, {
        "clean": {"minutes": 4},
        "mix": {"extra": 16},
        "doctor": {"at": at, "early": 0},
    }, ["excess", "late_n"])


def sample_gate(rng: random.Random) -> dict:
    flights = []
    t = 0
    wides = set(rng.sample(range(8), 3))
    for i, name in enumerate("ABCDEFGH"):
        dur = rng.randint(28, 42)
        flights.append({
            "id": name,
            "arr": t,
            "dep": t + dur,
            "wide": i in wides,
            "pax": rng.randint(30, 160),
        })
        t += rng.randint(10, 18)
    gates = []
    for i in range(4):
        adj = []
        if i:
            adj.append(f"G{i}")
        if i < 3:
            adj.append(f"G{i + 2}")
        gates.append({"id": f"G{i + 1}", "remote": False, "bus": 0, "adj": adj})
    for i, bus in enumerate((6, 9, 12, 15)):
        gates.append({"id": f"G{i + 5}", "remote": True, "bus": bus, "adj": []})
    width = rng.choice([30, 40])
    return _world(gate.FAMILY, {"flights": flights, "gates": gates}, {
        "wide": {},
        "wave": {"width": width, "extra": rng.choice([4, 6, 8])},
    }, ["pax_bus", "remote_n"])


# bite：新模块必须改变最优主值。salient：模型上次用来拿满分的那类做法，必须只拿到 4 分。
HUNTS = [
    ("signal", signal.FAMILY, sample_signal, 40, None, None, 10**9),
    ("deice", deice.FAMILY, sample_deice, 6, "flush", deice.greedy_batch, 12),
    ("line", line.FAMILY, sample_line, 12, None, None, 10**9),
    ("kitchen", kitchen.FAMILY, sample_kitchen, 8, "pan", kitchen.greedy_short, 64),
    ("charge", charge.FAMILY, sample_charge, 6, "block", charge.greedy_depart, 16),
    ("ward", ward.FAMILY, sample_ward, 12, "mix", ward.greedy_batch, 64),
    ("gate", gate.FAMILY, sample_gate, 80, "wave", gate.greedy_pax, 16),
]




def main() -> int:
    only = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    selected = [h for h in HUNTS if not only or h[0] in only]
    for name, fam, sample, gap, bite, salient, max_opt in selected:
        hit = None
        for seed in range(400):
            if seed and seed % 50 == 0:
                print(f"... {name} {seed}", flush=True)
            world = sample(random.Random(seed))
            got = _trap(fam, world, gap, bite=bite, salient=salient, max_opt=max_opt)
            if got:
                hit = (seed, world, got)
                break
        if hit is None:
            print(f"MISS {name}")
            continue
        seed, world, got = hit
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(world, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        found[name] = {"seed": seed, **got}
        print(f"KEEP {name} seed={seed} optimal={got['optimal']} greedy={got['greedy']} trap={got['plan']}")

    if not only:
        copies = {
            "delivery": OLD / "delivery-极难-3308.json",
            "trip": OLD / "trip-极难-8201.json",
            "elevator": OLD / "elevator-极难-7101.json",
        }
        for name, src in copies.items():
            shutil.copy(src, OUT / f"{name}.json")
            print(f"COPY {name}")

    (ROOT / "out/worldkit").mkdir(parents=True, exist_ok=True)
    stamp = "scenes10_hunt.json" if not only else "scenes10_harden_" + "_".join(only) + ".json"
    (ROOT / "out/worldkit" / stamp).write_text(
        json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"found {len(found)} / {len(selected)}")
    return 0 if len(found) == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
