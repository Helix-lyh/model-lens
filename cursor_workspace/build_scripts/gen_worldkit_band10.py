#!/usr/bin/env python3
"""猎三道新形状极难题：显眼贪心答对 4 分那一问，方案、主值和反事实都错。"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.worldkit import answers, core, render  # noqa: E402
from eval_bank_20260925.worldkit.families import evac, quay, repair  # noqa: E402

OUT = ROOT / "eval_bank_20260925/worldkit/worlds/band10"
BUDGET = core.Budget(80_000, 60)


def _world(fam, data, modules, objective) -> dict:
    return {
        "family": fam.id,
        "data": data,
        "modules": modules,
        "objective": objective,
        "questions": fam.questions(),
        "background": [],
    }


def _trap(fam, world: dict, min_gap: int, *, bite: str | None = None, max_opt: int = 16):
    sol = core.solve(fam, world, BUDGET)
    if sol.status != "ok" or len(sol.optimal) > max_opt:
        return None
    if bite:
        import copy
        bare = copy.deepcopy(world)
        bare["modules"].pop(bite, None)
        bsol = core.solve(fam, bare, BUDGET)
        if bsol.status != "ok" or bsol.best.metrics[fam.primary] == sol.best.metrics[fam.primary]:
            return None
    key = core.answers(fam, world)
    cf_world = fam.counterfactuals[fam.cf_key].transform(world)
    cf_sol = core.solve(fam, cf_world, BUDGET)
    if cf_sol.status != "ok":
        return None
    if cf_sol.best.metrics[fam.primary] == sol.best.metrics[fam.primary]:
        return None
    for gplan in fam.greedies(world):
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
        scored = answers.score(fam, world, key, "ANSWER: " + "; ".join(parts), best=sol.best)
        if scored["points"] != 4:
            continue
        if render.leaks(render.render_prompt(fam, world)):
            continue
        ref = answers.score(
            fam, world, key,
            answers.reference_text(world, key, core.Solver(fam, BUDGET), best=sol.best),
            best=sol.best,
        )
        if not ref["passed"]:
            continue
        return {
            "plan": list(gplan),
            "points": 4,
            "n_opt": len(sol.optimal),
            "optimal": dict(sol.best.metrics),
            "greedy": dict(gout.metrics),
            "opt_plan": list(sol.best.plan),
        }
    return None


def sample_quay(rng: random.Random) -> dict:
    cargos = ["粮", "箱", "油"]
    ships = []
    long_n = 0
    for name in "ABCDEF":
        long = rng.random() < 0.45
        if long:
            long_n += 1
        length = rng.choice([140, 155, 170]) if long else rng.choice([70, 85, 100])
        arrive = rng.choice([0, 2, 4, 6, 8, 10])
        work = rng.randint(5, 11)
        ships.append({
            "id": name,
            "length": length,
            "arrive": arrive,
            "work": work,
            "due": arrive + work + rng.randint(10, 28),
            "cargo": rng.choice(cargos),
        })
    if long_n < 2:
        ships[0]["length"] = 160
        ships[1]["length"] = 150
    lo = rng.choice([4, 8, 12])
    return _world(quay.FAMILY, {
        "tug": rng.choice([3, 4, 5]),
        "berths": [{"id": "1", "length": 180}, {"id": "2", "length": 110}],
        "ships": ships,
    }, {
        "tide": {"berth": "1", "lo": lo, "hi": lo + rng.choice([8, 12, 16])},
        "flush": {"minutes": rng.choice([4, 6, 8])},
        "swell": {"extra": rng.choice([2, 3, 4])},
    }, ["tardiness", "late_n"])


def sample_evac(rng: random.Random) -> dict:
    groups = []
    slow = []
    for name in "ABCDEF":
        near = rng.choice(["1", "2"])
        far = "2" if near == "1" else "1"
        walk_near = rng.choice([0, 1, 2])
        walk_far = walk_near + rng.choice([4, 6, 8])
        size = rng.randint(3, 7)
        due = walk_near + rng.randint(3, 10)
        groups.append({
            "id": name,
            "size": size,
            "walk": {near: walk_near, far: walk_far},
            "due": due,
        })
        if rng.random() < 0.35:
            slow.append(name)
    if len(slow) < 2:
        slow = ["A", "C"]
    lo = rng.choice([4, 6, 8])
    return _world(evac.FAMILY, {
        "stairs": [{"id": "1", "cap": rng.choice([2, 3])}, {"id": "2", "cap": rng.choice([2, 3])}],
        "groups": groups,
    }, {
        "smoke": {"stair": "2", "lo": lo, "hi": lo + rng.choice([6, 10, 14])},
        "slow": {"ids": slow},
        "drill": {"extra": rng.choice([1, 2])},
    }, ["delay", "late_n"])


def sample_repair(rng: random.Random) -> dict:
    sites = ["P", "Q", "R"]
    jobs = []
    skills = ["线", "线", "线", "线", "变", "变"]
    rng.shuffle(skills)
    for name, skill in zip("ABCDEF", skills):
        site = rng.choice(sites)
        work = rng.randint(3, 7)
        jobs.append({
            "id": name,
            "site": site,
            "skill": skill,
            "work": work,
            "due": rng.randint(10, 28),
        })
    if sum(j["site"] == "P" for j in jobs) < 2:
        jobs[0]["site"] = jobs[1]["site"] = "P"
    travel = {a: {} for a in ["0", *sites]}
    for a in travel:
        for b in travel:
            if a == b:
                travel[a][b] = 0
            else:
                travel[a][b] = rng.choice([2, 3, 4, 5])
    return _world(repair.FAMILY, {
        "depot": "0",
        "crews": [
            {"id": "1", "skills": ["线"]},
            {"id": "2", "skills": ["线", "变"]},
        ],
        "jobs": jobs,
        "travel": travel,
    }, {
        "clash": {},
        "fatigue": {"at": rng.choice([8, 10, 12, 14])},
        "extra": {"extra": rng.choice([1, 2])},
    }, ["late", "late_n"])


HUNTS = [
    ("quay", quay.FAMILY, sample_quay, 8, "tide"),
    ("evac", evac.FAMILY, sample_evac, 6, "smoke"),
    ("repair", repair.FAMILY, sample_repair, 6, "fatigue"),
]


def main() -> int:
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    selected = [h for h in HUNTS if not only or h[0] in only]
    seeds = 600
    for name, fam, sample, gap, bite in selected:
        hit = None
        for seed in range(seeds):
            if seed and seed % 40 == 0:
                print(f"... {name} {seed}", flush=True)
            world = sample(random.Random(seed))
            try:
                got = _trap(fam, world, gap, bite=bite)
            except Exception as exc:
                print(f"ERR {name} seed={seed} {exc}", flush=True)
                continue
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
        print(f"KEEP {name} seed={seed} optimal={got['optimal']} greedy={got['greedy']} "
              f"trap={got['plan']} opt={got['opt_plan']}", flush=True)

    (ROOT / "out/worldkit").mkdir(parents=True, exist_ok=True)
    stamp = "band10_hunt.json" if not only else "band10_hunt_" + "_".join(only) + ".json"
    (ROOT / "out/worldkit" / stamp).write_text(
        json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"found {len(found)} / {len(selected)}")
    return 0 if len(found) == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
