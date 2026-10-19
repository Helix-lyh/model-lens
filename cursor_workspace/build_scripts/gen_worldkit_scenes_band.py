#!/usr/bin/env python3
"""每场景一道：启发式自洽答卷落在 2–6 分。已实测在区间内的世界直接沿用。"""
from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.worldkit import band  # noqa: E402
from eval_bank_20260925.worldkit.families import (  # noqa: E402
    charge, cycle, deice, gate, kitchen, push, ramp, shift, signal, triage, ward, yard,
)
from cursor_workspace.build_scripts import gen_worldkit_scenes10 as g10  # noqa: E402

OUT = ROOT / "eval_bank_20260925/worldkit/worlds/scenes_band"
KEEP = ROOT / "eval_bank_20260925/worldkit/worlds/scenes20"


def sample_charge(rng: random.Random) -> dict:
    world = g10.sample_charge(rng)
    block = world["modules"]["block"]
    block["alt_hi"] = block["hi"] + rng.choice([6, 8, 10, 12])
    qs = charge.FAMILY.questions()
    for q in qs:
        if q.get("cf"):
            q["cf"] = "block_shift"
    world["questions"] = qs
    return world


def sample_signal(rng: random.Random) -> dict:
    world = g10.sample_signal(rng)
    off = world["modules"]["offset"]
    width = off["hi"] - off["lo"]
    off["alt_lo"] = off["lo"] + rng.choice([6, 10, 14])
    off["alt_hi"] = off["alt_lo"] + width
    qs = signal.FAMILY.questions()
    for q in qs:
        if q.get("cf"):
            q["cf"] = "offset_shift"
    world["questions"] = qs
    return world


def sample_ward(rng: random.Random) -> dict:
    world = g10.sample_ward(rng)
    world["data"]["patients"] = world["data"]["patients"][:7]
    world["modules"]["nurse"] = {}
    world["questions"] = ward.FAMILY.questions()
    return world


def sample_kitchen(rng: random.Random) -> dict:
    world = g10.sample_kitchen(rng)
    world["data"]["dishes"] = world["data"]["dishes"][:7]
    world["modules"]["gas"] = {}
    pan = world["modules"]["pan"]
    pan["alt"] = pan["minutes"] + rng.choice([6, 10, 14])
    qs = kitchen.FAMILY.questions()
    for q in qs:
        if q.get("cf"):
            q["cf"] = "pan_shift"
    world["questions"] = qs
    return world


def sample_deice(rng: random.Random) -> dict:
    world = g10.sample_deice(rng)
    world["data"]["planes"] = world["data"]["planes"][:7]
    world["modules"]["pump"] = {}
    flush = world["modules"]["flush"]
    flush["alt"] = flush["minutes"] + rng.choice([4, 6, 8])
    qs = deice.FAMILY.questions()
    for q in qs:
        if q.get("cf"):
            q["cf"] = "flush_shift"
    world["questions"] = qs
    return world


def sample_gate(rng: random.Random) -> dict:
    world = g10.sample_gate(rng)
    world["data"]["flights"] = world["data"]["flights"][:6]
    world["data"]["gates"] = world["data"]["gates"][:6]
    world["modules"]["tow"] = {"minutes": rng.choice([24, 28, 32]), "alt": rng.choice([40, 48, 56])}
    qs = gate.FAMILY.questions()
    for q in qs:
        if q.get("cf"):
            q["cf"] = "tow_shift"
    world["questions"] = qs
    return world


def sample_push(rng: random.Random) -> dict:
    zones = ["东", "西", "北"]
    flights = []
    letters = "ABCDEFG"
    for i, name in enumerate(letters):
        flights.append({
            "id": name,
            "dep": rng.randint(10, 28),
            "tow": rng.randint(4, 9),
            "zone": zones[i % 3],
            "wide": i in (0, 4),
        })
    gap = rng.choice([4, 6, 8])
    return {
        "family": "push",
        "data": {"flights": flights},
        "modules": {
            "share": {},
            "zone": {"minutes": gap, "alt": gap + rng.choice([6, 8, 10])},
            "wide": {"extra": rng.choice([3, 4])},
        },
        "objective": ["flow", "late_n"],
        "questions": push.FAMILY.questions(),
        "background": [],
    }


def sample_yard(rng: random.Random) -> dict:
    ships = []
    for i, name in enumerate("ABCDE"):
        ships.append({
            "id": name,
            "seq": i,
            "boxes": rng.choice([3, 4, 5, 6]),
            "tide": rng.choice([12, 16, 20, 24, 28]),
        })
    n_waves = 3
    step = rng.choice([8, 10])
    thresh = rng.choice([5, 6, 7])
    return {
        "family": "yard",
        "data": {
            "n_waves": n_waves,
            "wave_end": [(i + 1) * step for i in range(n_waves)],
            "yards": [{"id": "X"}, {"id": "Y"}],
            "ships": ships,
        },
        "modules": {
            "wave": {"cap": rng.choice([6, 7, 8])},
            "yard": {"thresh": thresh, "slow": rng.choice([6, 8, 10]), "alt": thresh + rng.choice([3, 4, 5])},
        },
        "objective": ["over", "late_n"],
        "questions": yard.FAMILY.questions(),
        "background": [],
    }


def sample_shift(rng: random.Random) -> dict:
    jobs = []
    fams = "PQR"
    for i, name in enumerate("ABCDE"):
        jobs.append({
            "id": name,
            "seq": i,
            "family": fams[i % 3],
            "minutes": rng.choice([3, 4, 5, 6]),
            "due": rng.choice([10, 14, 18, 22, 26]),
        })
    step = rng.choice([8, 10])
    k = rng.choice([1, 2])
    cap = rng.choice([4, 5])
    return {
        "family": "shift",
        "data": {
            "n_waves": 3,
            "wave_end": [(i + 1) * step for i in range(3)],
            "cap": cap,
            "lines": [{"id": "X"}, {"id": "Y"}],
            "jobs": jobs,
        },
        "modules": {
            "lag": {"k": k, "slow": rng.choice([6, 8, 10]), "alt": k + rng.choice([1, 2])},
            "setup": {"minutes": rng.choice([2, 3, 4])},
        },
        "objective": ["over", "late_n"],
        "questions": shift.FAMILY.questions(),
        "background": [],
    }


def sample_cycle(rng: random.Random) -> dict:
    names = ["南北直行", "东西直行", "南北左转", "东西左转", "行人"]
    streams = []
    for i, name in enumerate(names):
        streams.append({"id": "ABCDE"[i], "name": name, "n": rng.choice([2, 3, 4, 5])})
    step = rng.choice([16, 20])
    lo = 0
    width = rng.choice([step, step + 4])
    return {
        "family": "cycle",
        "data": {
            "n_slots": 3,
            "slot_start": [i * step for i in range(3)],
            "greens": {"S": rng.choice([8, 10]), "L": rng.choice([16, 20])},
            "headway": rng.choice([4, 5]),
            "miss": rng.choice([12, 15, 18]),
            "streams": streams,
        },
        "modules": {
            "share": {},
            "offset": {"phase": "A", "lo": lo, "hi": lo + width,
                       "alt_lo": step, "alt_hi": step + width},
            "rain": {"extra": rng.choice([1, 2])},
        },
        "objective": ["delay", "wait_n"],
        "questions": cycle.FAMILY.questions(),
        "background": [],
    }


def sample_triage(rng: random.Random) -> dict:
    grades = ["隔离", "普通"]
    patients = []
    for i, name in enumerate("ABCDE"):
        patients.append({
            "id": name,
            "seq": i,
            "grade": grades[i % 2],
            "care": rng.choice([3, 4, 5, 6]),
            "limit": rng.choice([10, 14, 18, 22, 26]),
        })
    step = rng.choice([8, 10])
    extra = rng.choice([2, 3, 4])
    return {
        "family": "triage",
        "data": {
            "n_slots": 3,
            "slot_end": [(i + 1) * step for i in range(3)],
            "beds": [{"id": "N"}, {"id": "I"}],
            "patients": patients,
        },
        "modules": {
            "slot": {"cap": rng.choice([6, 7, 8])},
            "mix": {"extra": extra, "alt": extra + rng.choice([3, 4, 5])},
        },
        "objective": ["excess", "late_n"],
        "questions": triage.FAMILY.questions(),
        "background": [],
    }


def sample_apron(rng: random.Random) -> dict:
    zones = ["东", "西", "北"]
    flights = []
    for i, name in enumerate("ABCDE"):
        flights.append({
            "id": name,
            "seq": i,
            "dep": rng.choice([10, 14, 18, 22, 26]),
            "tow": rng.choice([3, 4, 5, 6]),
            "zone": zones[i % 3],
        })
    step = rng.choice([8, 10])
    gap = rng.choice([2, 3, 4])
    return {
        "family": "ramp",
        "data": {
            "n_waves": 3,
            "wave_end": [(i + 1) * step for i in range(3)],
            "tractors": [{"id": "X"}, {"id": "Y"}],
            "flights": flights,
        },
        "modules": {
            "wave": {"cap": rng.choice([6, 7, 8])},
            "zone": {"minutes": gap, "alt": gap + rng.choice([3, 4, 5])},
        },
        "objective": ["flow", "late_n"],
        "questions": ramp.FAMILY.questions(),
        "background": [],
    }


# 除冰全排列、机位指派默认不猎：实测 15/20。需要时显式传入名字。
HUNTS = [
    ("signal", signal.FAMILY, sample_signal, "offset"),
    ("kitchen", kitchen.FAMILY, sample_kitchen, "gas"),
    ("push", push.FAMILY, sample_push, "zone"),
    ("yard", yard.FAMILY, sample_yard, "yard"),
]
RETIRED = [
    ("deice", deice.FAMILY, sample_deice, "pump"),
    ("gate", gate.FAMILY, sample_gate, "tow"),
    ("charge", charge.FAMILY, sample_charge, "block"),
    ("ward", ward.FAMILY, sample_ward, "mix"),
]


def main() -> int:
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    copies = {
        "delivery": KEEP / "delivery.json",
        "trip": KEEP / "trip.json",
        "elevator": KEEP / "elevator.json",
        "line": KEEP / "line.json",
    }
    pool = HUNTS + RETIRED
    selected = [h for h in pool if (not only and h in HUNTS) or (only and h[0] in only)]
    for name, src in copies.items():
        if only and name not in only:
            continue
        if name == "line" and any(h[0] == "line" for h in selected):
            continue
        shutil.copy(src, OUT / f"{name}.json")
        found[name] = {"copied": str(src.relative_to(ROOT)), "live_points": {"delivery": 4, "trip": 4, "elevator": 4, "line": 5}[name]}
        print(f"COPY {name}")

    for name, fam, sample, bite in selected:
        hit = None
        for seed in range(500):
            if seed and seed % 25 == 0:
                print(f"... {name} {seed}", flush=True)
            world = sample(random.Random(seed))
            try:
                got = band.accept(fam, world, bite=bite)
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
        (OUT / f"{name}.json").write_text(json.dumps(world, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        found[name] = {"seed": seed, **{k: got[k] for k in ("optimal", "n_opt", "n_primary", "n_shared", "heuristics", "cf")}}
        pts = [h["points"] for h in got["heuristics"]]
        print(f"KEEP {name} seed={seed} heur={pts} n_shared={got['n_shared']}/{got['n_feasible']} "
              f"n_primary={got['n_primary']}/{got['n_feasible']}", flush=True)

    (ROOT / "out/worldkit").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/worldkit" / "scenes_band_hunt.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    missed = [h[0] for h in selected if h[0] not in found]
    print(f"found {len(found)} missed {missed}")
    return 0 if not missed else 1


ASSIGN_HUNTS = [
    ("line", shift.FAMILY, sample_shift, "lag"),
    ("signal", cycle.FAMILY, sample_cycle, "share"),
    ("ward", triage.FAMILY, sample_triage, "mix"),
    ("push", ramp.FAMILY, sample_apron, "zone"),
]


def hunt_assign() -> int:
    dest = ROOT / "out/worldkit/assign_hunt"
    dest.mkdir(parents=True, exist_ok=True)
    found = {}
    candidates = []
    for name, fam, sample, bite in ASSIGN_HUNTS:
        hit = None
        for seed in range(500):
            if seed and seed % 25 == 0:
                print(f"... {name} {seed}", flush=True)
            world = sample(random.Random(seed))
            try:
                got = band.accept(fam, world, bite=bite)
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
        (dest / f"{name}.json").write_text(json.dumps(world, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        found[name] = {"seed": seed, **{k: got[k] for k in ("optimal", "n_opt", "n_primary", "n_shared", "heuristics", "cf")}}
        pts = [h["points"] for h in got["heuristics"]]
        print(f"KEEP {name} seed={seed} heur={pts} n_shared={got['n_shared']}/{got['n_feasible']} "
              f"n_primary={got['n_primary']}/{got['n_feasible']}", flush=True)
        candidates.append({"id": name, "tier": "assign", "world": world})
    (ROOT / "out/worldkit").mkdir(parents=True, exist_ok=True)
    (ROOT / "out/worldkit/scenes_band_assign.json").write_text(
        json.dumps({"candidates": candidates}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (ROOT / "out/worldkit/scenes_band_assign_hunt.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    missed = [h[0] for h in ASSIGN_HUNTS if h[0] not in found]
    print(f"found {len(found)} missed {missed}")
    return 0 if not missed else 1


if __name__ == "__main__":
    if "--assign" in sys.argv:
        raise SystemExit(hunt_assign())
    raise SystemExit(main())

