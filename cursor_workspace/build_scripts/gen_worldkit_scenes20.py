#!/usr/bin/env python3
"""为十五个分段选择场景各冻一道极难题，并拼上已落在约 4 到 9 分的五道扩展题。

逐段贪心只看翻倍后的作业分钟。它的费用与最优相同，完成时刻、反事实和逐段加总都对不上。
"""
from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cursor_workspace.build_scripts.gen_worldkit_scenes10 import _trap, _world  # noqa: E402
from eval_bank_20260925.worldkit import answers, core  # noqa: E402
from eval_bank_20260925.worldkit.families.cascade import FAMILIES, SPECS, greedy_local  # noqa: E402

OUT = ROOT / "eval_bank_20260925/worldkit/worlds/scenes20"
SRC = ROOT / "eval_bank_20260925/worldkit/worlds/scenes10"
KEEP = ("delivery", "trip", "elevator", "signal", "line")

def _seg(rng: random.Random, lo: int, hi: int, lights: bool) -> dict:
    row = {"min": rng.randint(lo, hi)}
    if lights:
        row["lights"] = True
    return row


def sample(spec: dict, rng: random.Random) -> dict:
    fam = FAMILIES[spec["id"]]
    by = {c["kind"]: c for c in spec["choices"]}
    fast, plain, timed = by["surge"], by["skip"], by["meet"]
    modes = [
        {"id": fast["id"], "label": fast["label"], "kind": "fast"},
        {"id": plain["id"], "label": plain["label"], "kind": "plain"},
        {"id": timed["id"], "label": timed["label"], "kind": "timed"},
    ]
    routes = [{"id": "DIRECT", "label": "直达"}, {"id": "DETOUR", "label": "绕行"}]
    legs = []
    for name in spec["stages"]:
        legs.append({
            "name": name,
            fast["id"]: {
                "DIRECT": [_seg(rng, 2, 4, True)],
                "DETOUR": [_seg(rng, 3, 6, False)],
            },
            plain["id"]: {
                "DIRECT": [_seg(rng, 8, 14, True)],
                "DETOUR": [_seg(rng, 12, 18, False)],
            },
            timed["id"]: {
                "DIRECT": {"access": rng.randint(1, 2), "ride": rng.randint(3, 6)},
                "DETOUR": {"access": rng.randint(2, 4), "ride": rng.randint(5, 9)},
            },
        })
    step = rng.choice((7, 8, 9))
    modules = {
        "surge": {"ids": [fast["id"]], "factor": 2},
        "wave": {"ids": [fast["id"], plain["id"]], "cycle": 10, "open": 4},
        "seam": {"minutes": rng.randint(4, 7)},
        "board": {"ids": [timed["id"]], "times": list(range(3, 120, step))},
    }
    data = {
        "modes": modes,
        "routes": routes,
        "legs": legs,
        "cost": {fast["id"]: 2, plain["id"]: 0, timed["id"]: 3},
    }
    return _world(fam, data, modules, ["time", "cost"])


def _local_miss(fam, world, sol) -> dict | None:
    plan = greedy_local(world)
    out = fam.simulate(world, plan)
    if out is None or "wave" not in out.fired:
        return None
    local = fam.local_clock(world, plan)
    bare = fam.counterfactuals["no_surge"].transform(world)
    local_cf = fam.local_clock(bare, plan)
    if local is None or local_cf is None:
        return None
    if local == sol.best.metrics["time"] or local == out.metrics["time"]:
        return None
    cf = core.solve(fam, bare)
    if cf.status != "ok" or local_cf == cf.best.metrics["time"]:
        return None
    parts = [ "-".join(plan), str(local), str(out.metrics["cost"]), str(local_cf) ]
    text = "ANSWER: " + "; ".join(parts)
    key = core.answers(fam, world)
    scored = answers.score(fam, world, key, text, best=sol.best)
    if scored["points"] != 4:
        return None
    return {"local_time": local, "local_cf": local_cf}


def main() -> int:
    only = set(sys.argv[1:])
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    specs = [s for s in SPECS if not only or s["id"] in only]
    for spec in specs:
        fam = FAMILIES[spec["id"]]
        hit = None
        for seed in range(400):
            if seed and seed % 80 == 0:
                print(f"... {spec['id']} {seed}", flush=True)
            world = sample(spec, random.Random(f"{spec['id']}:{seed}"))
            got = _trap(fam, world, 1, bite="surge", max_opt=12)
            if not got:
                continue
            sol = core.solve(fam, world)
            extra = _local_miss(fam, world, sol)
            if extra is None:
                continue
            hit = (seed, world, got, extra)
            break
        if hit is None:
            print(f"MISS {spec['id']}")
            continue
        seed, world, got, extra = hit
        (OUT / f"{spec['id']}.json").write_text(
            json.dumps(world, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        found[spec["id"]] = {"seed": seed, **got, **extra}
        print(f"KEEP {spec['id']} seed={seed} n_opt={got['n_opt']} optimal={got['optimal']} "
              f"greedy={got['greedy']} local={extra['local_time']}/{extra['local_cf']}")

    if not only:
        for name in KEEP:
            shutil.copy(SRC / f"{name}.json", OUT / f"{name}.json")
            print(f"COPY {name}")

    (ROOT / "out/worldkit").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/worldkit/scenes20_hunt.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"found {len(found)} / {len(specs)}")
    return 0 if len(found) == len(specs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
