#!/usr/bin/env python3
"""worldkit 候选题实测：对候选题（含无解题的近邻）与 NX 预设逐题请求模型并机械判分。

  .venv/bin/python cursor_workspace/build_scripts/try_worldkit_live.py \
      --candidates out/worldkit/delivery_candidates.json --n 2

默认渠道读环境变量 BOOSTER_BASE_URL / BOOSTER_API_KEY，模型 deepseek-flash。结果写 out/worldkit/live_<model>.json。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.evaluation import is_timeout_error  # noqa: E402
from eval_bank_20260925.worldkit import accel, answers, core, render, sample  # noqa: E402
from eval_bank_20260925.worldkit.families import family_of  # noqa: E402
from src.client import ChatClient, JsonlRecorder  # noqa: E402
from src.types import Endpoint  # noqa: E402


def _items(paths: list[Path], presets: bool) -> list[dict]:
    out = []
    for p in paths:
        for c in json.loads(p.read_text(encoding="utf-8"))["candidates"]:
            label = c.get("id") or f"{c['tier']}#{c['seed']}"
            out.append({"id": label, "tier": c["tier"], "world": c["world"],
                         "key": c.get("answer"), "prompt": c.get("prompt")})
            if "twin" in c:
                out.append({"id": f"{label}-近邻", "tier": c["tier"] + "-近邻",
                            "world": c["twin"]["world"], "key": c["twin"].get("answer"), "prompt": c["twin"].get("prompt")})
    if presets:
        for p in sorted((sample.WORLDS / "delivery/presets").glob("*.json")):
            out.append({"id": p.stem, "tier": "复现", "world": json.loads(p.read_text(encoding="utf-8"))})
    for it in out:
        fam = family_of(it["world"])
        if not it.get("key"):
            solver = core.Solver(fam, core.Budget(400_000, 120))
            it["key"] = core.answers(fam, it["world"], solver)
        if not it.get("prompt"):
            it["prompt"] = render.render_prompt(fam, it["world"])
    return out


def _best_outcome(fam, world: dict) -> core.Outcome | None:
    """配送用 Go 拿最优路线再重放；其余题族方案数小，直接用 Python 求解。"""
    if fam.id != "delivery":
        sol = core.solve(fam, world)
        return sol.best if sol.status == "ok" else None
    try:
        st = accel.status(world, max_plans=400_000, seconds=180)
    except Exception:
        return None
    if st.get("error") or st.get("status") != "ok" or not st.get("plan"):
        return None
    plan = tuple(st["plan"])
    return fam.simulate(fam.effective(world), plan)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", nargs="*", type=Path, default=[ROOT / "out/worldkit/delivery_candidates.json"])
    ap.add_argument("--no-presets", action="store_true")
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--base-url-env", default="BOOSTER_BASE_URL")
    ap.add_argument("--key-env", default="BOOSTER_API_KEY")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--summary", type=Path, default=None)
    a = ap.parse_args()

    items = _items(a.candidates, not a.no_presets)
    ep = Endpoint(base_url=os.environ[a.base_url_env], api_key_env=a.key_env, model=a.model)
    out_dir = ROOT / "out/worldkit"
    client = ChatClient(ep, JsonlRecorder(out_dir / f"live_{a.model}.jsonl"), timeout_s=a.timeout, max_retries=1)
    def one(job):
        it, i = job
        fam = family_of(it["world"])
        rec = client.complete([{"role": "user", "content": it["prompt"]}], temperature=0.0, max_tokens=None,
                              kind=f"worldkit:{it['id']}:n{i}")
        if rec.error or not rec.content:
            detail = rec.error or f"http {rec.status_code}"
            if is_timeout_error(rec.error, rec.status_code):
                groups = [{"name": q["name"], "points": 0, "max": q["points"]} for q in it["world"]["questions"]]
                return it["id"], i, {
                    "status": "fail", "reason_code": "timeout", "passed": False,
                    "points": 0, "points_total": 20, "score10": 0.0, "detail": detail, "groups": groups,
                }
            return it["id"], i, {"status": "missing", "detail": detail}
        try:
            solver = core.Solver(fam, core.Budget(400_000, 180))
            best = _best_outcome(fam, it["world"])
            r = answers.score(fam, it["world"], it["key"], rec.content, solver, best=best)
        except Exception as exc:
            return it["id"], i, {"status": "missing", "detail": f"score_error: {exc}"}
        r["tail"] = rec.content[-300:]
        return it["id"], i, r

    jobs = [(it, i) for it in items for i in range(a.n)]
    results: dict[str, list] = {it["id"]: [] for it in items}
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for iid, i, r in pool.map(one, jobs):
            results[iid].append(r)
            g = " ".join(f"{x['name']}={x['points']}/{x['max']}" for x in r.get("groups", []))
            print(f"{iid} n{i}: {r['status']} {r.get('points', '-')}/20 {g} {r.get('reason_code', r.get('detail', ''))}",
                  flush=True)

    summary = []
    for it in items:
        rs = [r for r in results[it["id"]] if r["status"] != "missing"]
        pts = [r["points"] for r in rs]
        summary.append({"id": it["id"], "tier": it["tier"], "answer": it["key"], "samples": len(rs),
                        "pass": sum(r["passed"] for r in rs), "mean_points": round(sum(pts) / len(pts), 1) if pts else None,
                        "results": results[it["id"]]})
    summary_path = a.summary or (out_dir / f"live_{a.model}.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n档位\t题\t通过/样本\t平均分")
    for s in summary:
        print(f"{s['tier']}\t{s['id']}\t{s['pass']}/{s['samples']}\t{s['mean_points']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
