#!/usr/bin/env python3
"""worldkit 配送场景：导出复现预设、按难度档生成候选题。

用法：
  .venv/bin/python cursor_workspace/build_scripts/gen_worldkit_delivery.py --presets
      从冻结的 reasoning_20261023.json 导出 NX-12/18 世界到 worlds/delivery/presets/
  .venv/bin/python cursor_workspace/build_scripts/gen_worldkit_delivery.py --check
      预设重跑门禁，答案须等于冻结值
  .venv/bin/python cursor_workspace/build_scripts/gen_worldkit_delivery.py --tiers 简单 中等 --want 2
      生成候选，写到 out/worldkit/delivery_candidates.json（out/ 不进 git）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.worldkit import answers, core, gates, legacy, render, sample  # noqa: E402
from eval_bank_20260925.worldkit.families import delivery  # noqa: E402

FROZEN = ROOT / "eval_bank_20260925/reasoning_20261023.json"
PRESETS = sample.WORLDS / "delivery" / "presets"
OUT = ROOT / "out/worldkit/delivery_candidates.json"


def _frozen() -> dict:
    return {r["item_id"]: r for r in json.loads(FROZEN.read_text(encoding="utf-8"))["items"]}


def export_presets() -> None:
    PRESETS.mkdir(parents=True, exist_ok=True)
    rows = _frozen()
    for iid in ("NX-12", "NX-18"):
        w = dict(legacy.world_from_nx(iid, rows[iid]["instance"]), gates={"min_degree": 3})
        (PRESETS / f"{iid}.json").write_text(json.dumps(w, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", PRESETS / f"{iid}.json")


def check_presets() -> int:
    rows, bad = _frozen(), 0
    for path in sorted(PRESETS.glob("*.json")):
        w = json.loads(path.read_text(encoding="utf-8"))
        t = time.time()
        rep = gates.run_gates(delivery.FAMILY, w)
        want = rows[path.stem]["answer"]
        ok = rep["accept"] and rep["answer"] == want
        bad += not ok
        print(f"{path.stem}: {'OK' if ok else 'FAIL'} answer={rep['answer']} frozen={want} "
              f"reasons={rep['reasons']} readings={rep.get('readings')} {time.time() - t:.1f}s")
    return 1 if bad else 0


def _candidate(item: dict) -> dict:
    fam = delivery.FAMILY
    w = item["world"]
    solver = core.Solver(fam, core.Budget(400_000, 120))
    key = core.answers(fam, w, solver)
    row = {
        "tier": item["tier"], "seed": item["seed"], "world": w,
        "prompt": render.render_prompt(fam, w),
        "answer": key, "reference": answers.reference_text(w, key, solver),
        "gates": {k: item["gates"].get(k) for k in ("checks", "search", "degree", "conflict", "boundary",
                                                     "readings", "fired")},
    }
    if item.get("depth"):
        row["depth"] = item["depth"]
    if "twin" in item:
        tw = item["twin"]["world"]
        tkey = core.answers(fam, tw, solver)
        row["twin"] = {"change": item["twin"]["change"], "world": tw, "prompt": render.render_prompt(fam, tw),
                       "answer": tkey, "reference": answers.reference_text(tw, tkey, solver)}
    return row


def generate(tiers: list[str], want: int, seed0: int, max_tries: int, out: Path = OUT) -> None:
    cfg = sample.load_config("delivery")
    rows, hist = [], {}
    for tier in tiers:
        t = time.time()
        res = sample.generate(cfg, tier, delivery.sample, delivery.perturbations, want, seed0, max_tries, log=print)
        hist[tier] = {"tries": res["tries"], "accepted": len(res["items"]), "rejections": res["rejections"],
                      "seconds": round(time.time() - t, 1)}
        print(tier, hist[tier])
        rows += [_candidate(it) for it in res["items"]]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"candidates": rows, "histogram": hist}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print("wrote", out, len(rows), "candidates")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--presets", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--tiers", nargs="*", default=[])
    ap.add_argument("--want", type=int, default=1)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--max-tries", type=int, default=400)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.presets:
        export_presets()
    if a.check:
        return check_presets()
    if a.tiers:
        generate(a.tiers, a.want, a.seed0, a.max_tries, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
