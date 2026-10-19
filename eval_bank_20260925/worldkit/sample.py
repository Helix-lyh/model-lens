"""按难度向量采样世界、跑门禁筛选；无解档同时寻找只改一个参数的近邻可解题。"""
from __future__ import annotations

import collections
import json
import random
from pathlib import Path
from typing import Any, Callable

from eval_bank_20260925.worldkit import accel, depth
from eval_bank_20260925.worldkit.core import Budget

WORLDS = Path(__file__).with_name("worlds")


def load_config(world_id: str) -> dict:
    return json.loads((WORLDS / world_id / "config.json").read_text(encoding="utf-8"))


def _budget(tier: dict) -> Budget:
    return Budget(max_plans=tier.get("max_plans", 200_000), seconds=tier.get("seconds", 20.0))


def _limits(tier: dict) -> tuple[int, float]:
    b = _budget(tier)
    return b.max_plans, b.seconds


def _status(world: dict, tier: dict) -> dict:
    plans, seconds = _limits(tier)
    return accel.status(world, max_plans=plans, seconds=seconds)


def _gates(world: dict, tier: dict, fail_fast: bool) -> dict:
    plans, seconds = _limits(tier)
    return accel.run_gates(world, fail_fast=fail_fast, max_plans=plans, seconds=seconds)


def find_twin(world: dict, tier: dict, perturbations: Callable[[dict], list],
              max_gated: int = 6) -> tuple[dict, dict, str] | None:
    """无解题的近邻可解题：只改一个参数、门禁全部通过的第一个变体。
    每个可解变体都要跑全部单删与双删，故最多对 max_gated 个可解变体跑门禁。"""
    gated = 0
    for desc, alt in perturbations(world):
        if gated >= max_gated:
            break
        alt["gates"] = {**alt.get("gates", {}), "min_boundary": 0}
        st = _status(alt, tier)
        if st.get("error") or st["status"] != "ok":
            continue
        gated += 1
        if not _gates(alt, tier, True)["accept"]:
            continue
        rep = _gates(alt, tier, False)
        if rep["accept"]:
            return alt, rep, desc
    return None


def generate(cfg: dict, tier_name: str, sampler, perturbations, want: int, seed0: int, max_tries: int = 400,
             log: Callable[[str], Any] | None = None) -> dict:
    tier = cfg["tiers"][tier_name]
    hist: collections.Counter = collections.Counter()
    items = []
    tried = 0
    for k in range(max_tries):
        if len(items) >= want:
            break
        tried += 1
        seed = seed0 + k
        world = sampler(random.Random(seed), cfg, tier)
        if tier.get("depth"):
            world = depth.prepare(world, lambda w: _status(w, tier))
            if world is None:
                hist["depth:prepare"] += 1
                continue
        st = _status(world, tier)
        if st.get("error"):
            hist["rejected:budget"] += 1
            if log:
                log(f"{tier_name} seed {seed} rejected:budget")
            continue
        infeasible = st["status"] != "ok"
        if bool(tier.get("infeasible")) != infeasible:
            hist["infeasible" if infeasible else "feasible"] += 1
            if log:
                log(f"{tier_name} seed {seed} {'infeasible' if infeasible else 'feasible'}")
            continue
        rep = _gates(world, tier, True)
        if not rep["accept"]:
            for r in rep["reasons"]:
                hist[r.split(" (")[0]] += 1
            if log:
                log(f"{tier_name} seed {seed} {rep['reasons'][0]}")
            continue
        rep = _gates(world, tier, False)
        if tier.get("depth"):
            if not rep["accept"]:
                for r in rep["reasons"]:
                    hist[r.split(" (")[0]] += 1
                continue
            if any((rep.get("readings") or {}).values()):
                hist["readings"] += 1
                if log:
                    log(f"{tier_name} seed {seed} readings")
                continue
            report = depth.assess(world, tier, lambda w: _status(w, tier))
            if not report["ok"]:
                hist[report["reason"]] += 1
                if log:
                    log(f"{tier_name}: seed {seed} rejected {report['reason']}")
                continue
        item = {"seed": seed, "tier": tier_name, "world": world, "gates": rep}
        if tier.get("depth"):
            item["depth"] = {k: report[k] for k in ("butterfly", "trap", "distractor")}
        if infeasible:
            twin = find_twin(world, tier, perturbations)
            if twin is None:
                hist["no_twin"] += 1
                continue
            item["twin"] = {"world": twin[0], "gates": twin[1], "change": twin[2]}
        items.append(item)
        if log:
            log(f"{tier_name}: accepted seed {seed} after {k + 1} tries")
    return {"tier": tier_name, "items": items, "tries": tried, "rejections": dict(hist.most_common())}
