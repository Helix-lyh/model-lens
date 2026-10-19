#!/usr/bin/env python3
"""猎罐区加注极难题：显眼贪心答对 4 分那一问。默认找 3 个不同种子。"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.worldkit import answers, core, render  # noqa: E402
from eval_bank_20260925.worldkit.families import tank  # noqa: E402

OUT = ROOT / "eval_bank_20260925/worldkit/worlds/band10"
BUDGET = core.Budget(80_000, 90)
FAM = tank.FAMILY


def _world(data, modules) -> dict:
    return {
        "family": FAM.id,
        "data": data,
        "modules": modules,
        "objective": ["late", "late_n"],
        "questions": FAM.questions(),
        "background": [],
    }


def sample(rng: random.Random) -> dict:
    cars = [{"id": name, "need": rng.randint(3, 7), "depart": rng.randint(8, 30)} for name in "ABCDEFG"]
    cap = rng.choice([6, 8, 10, 12])
    return _world({"cars": cars}, {
        "tank": {"cap": cap, "refill": rng.choice([4, 6, 8])},
        "block": {"lo": 0, "hi": rng.choice([6, 8, 10, 12])},
        "extra": {"extra": rng.choice([2, 3])},
    })


def _trap(world: dict, min_gap: int = 8, max_opt: int = 16):
    sol = core.solve(FAM, world, BUDGET)
    if sol.status != "ok" or len(sol.optimal) > max_opt:
        return None
    key = core.answers(FAM, world)
    cf_world = FAM.counterfactuals[FAM.cf_key].transform(world)
    hit = None
    for gplan in FAM.greedies(world):
        gout = FAM.simulate(world, gplan)
        if gout is None:
            continue
        if core.objective_key(world, gout) == core.objective_key(world, sol.best):
            continue
        if gout.metrics[FAM.shared] != sol.best.metrics[FAM.shared]:
            continue
        if gout.metrics[FAM.primary] < sol.best.metrics[FAM.primary] + min_gap:
            continue
        gcf = FAM.simulate(cf_world, gplan)
        if gcf is None:
            continue
        cf_sol = core.solve(FAM, cf_world, BUDGET)
        if cf_sol.status != "ok":
            return None
        if cf_sol.best.metrics[FAM.primary] == sol.best.metrics[FAM.primary]:
            return None
        if gcf.metrics[FAM.primary] == cf_sol.best.metrics[FAM.primary]:
            continue
        parts = []
        for q in world["questions"]:
            if q.get("type") == "plan":
                parts.append("-".join(gplan))
            elif q.get("cf"):
                parts.append(str(gcf.metrics[FAM.primary]))
            else:
                parts.append(str(gout.metrics[q["metric"]]))
        scored = answers.score(FAM, world, key, "ANSWER: " + "; ".join(parts), best=sol.best)
        if scored["points"] != 4:
            continue
        if render.leaks(render.render_prompt(FAM, world)):
            continue
        ref = answers.score(
            FAM, world, key,
            answers.reference_text(world, key, core.Solver(FAM, BUDGET), best=sol.best),
            best=sol.best,
        )
        if not ref["passed"]:
            continue
        infinite = json.loads(json.dumps(world))
        infinite["modules"]["tank"] = {"cap": 10_000, "refill": 1}
        bsol = core.solve(FAM, infinite, BUDGET)
        if bsol.status != "ok" or bsol.best.metrics[FAM.primary] == sol.best.metrics[FAM.primary]:
            return None
        hit = {
            "plan": list(gplan),
            "points": 4,
            "n_opt": len(sol.optimal),
            "optimal": dict(sol.best.metrics),
            "greedy": dict(gout.metrics),
            "opt_plan": list(sol.best.plan),
        }
        break
    return hit


def main() -> int:
    want = 3
    OUT.mkdir(parents=True, exist_ok=True)
    found = []
    for seed in range(400):
        if len(found) >= want:
            break
        if seed and seed % 20 == 0:
            print(f"... tank {seed} kept {len(found)}", flush=True)
        world = sample(random.Random(seed))
        try:
            got = _trap(world)
        except Exception as exc:
            print(f"ERR seed={seed} {exc}", flush=True)
            continue
        if not got:
            continue
        name = "tank" if not found else f"tank{len(found) + 1}"
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(world, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        rec = {"id": name, "seed": seed, **got}
        found.append(rec)
        print(f"KEEP {name} seed={seed} optimal={got['optimal']} greedy={got['greedy']} "
              f"trap={got['plan']} opt={got['opt_plan']}", flush=True)

    (ROOT / "out/worldkit").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/worldkit" / "tank_hunt.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"found {len(found)} / {want}")
    return 0 if len(found) == want else 1


if __name__ == "__main__":
    raise SystemExit(main())
