"""2–6 分出题门禁。

实测形态：模型交一份自洽启发式答卷，分数 = 其中有几项碰巧等于参考值。
一条贪心恰好 4 分不够：模型常换启发式，或把反事实世界重新解对，于是 9–14 或 0。
本模块要求：列出的启发式自洽答卷都落在 [lo, hi]，最优主值不能被大量错方案共享，题面不要把封闭公式写出来。
"""
from __future__ import annotations

from eval_bank_20260925.worldkit import answers, core, render

BAND_LO = 4
BAND_HI = 8
# 主值等于最优的可行方案占比超过这个，错方案容易撞上 5 分问
MAX_PRIMARY_FRAC = 0.12
# 并列指标等于最优的占比超过这个，4 分问人人能撞
MAX_SHARED_FRAC = 0.95  # 4 分问本来就要让显眼贪心撞上；并泵除冰的额外除冰次数经常大面积为 0
FORMULA = ("开工时刻 =", "开始时刻 =", "靠泊开始时刻 =", "进入耗时 =", "向上取整", "出锅时刻 =")


def cf_question(world: dict) -> dict | None:
    for q in world["questions"]:
        if q.get("cf"):
            return q
    return None


def heuristic_plans(fam, world: dict) -> list[tuple]:
    fn = getattr(fam, "greedies", None)
    if fn is None:
        return []
    out = []
    seen = set()
    for plan in fn(world):
        if not plan or plan in seen:
            continue
        seen.add(plan)
        out.append(plan)
    return out


def closed_form(prompt: str) -> list[str]:
    return [t for t in FORMULA if t in prompt]


def accept(
    fam,
    world: dict,
    *,
    lo: int = BAND_LO,
    hi: int = BAND_HI,
    bite: str | None = None,
    budget: core.Budget | None = None,
) -> dict | None:
    """通过则返回猎题摘要；否则 None。"""
    budget = budget or core.Budget(80_000, 60)
    prompt = render.render_prompt(fam, world)
    if render.leaks(prompt) or closed_form(prompt):
        return None
    sol = core.solve(fam, world, budget)
    if sol.status != "ok" or sol.best is None:
        return None
    if sol.n_feasible <= 0:
        return None
    if sol.n_primary / sol.n_feasible > MAX_PRIMARY_FRAC:
        return None
    if sol.n_feasible and sol.n_shared / sol.n_feasible > MAX_SHARED_FRAC and sol.n_shared < sol.n_feasible:
        return None
    if bite and bite in world["modules"]:
        import copy
        bare = copy.deepcopy(world)
        bare["modules"].pop(bite)
        try:
            bsol = core.solve(fam, bare, budget)
        except Exception:
            return None
        if bsol.status != "ok" or bsol.best is None:
            return None
        if bsol.best.metrics[fam.primary] == sol.best.metrics[fam.primary]:
            return None
    cf_q = cf_question(world)
    if cf_q is None:
        return None
    cf_world = fam.counterfactuals[cf_q["cf"]].transform(world)
    cf_sol = core.solve(fam, cf_world, budget)
    if cf_sol.status != "ok" or cf_sol.best is None:
        return None
    if cf_sol.best.metrics[cf_q["metric"]] == sol.best.metrics[cf_q["metric"]]:
        return None
    key = core.answers(fam, world)
    plans = heuristic_plans(fam, world)
    if not plans:
        return None
    hits = []
    for plan in plans:
        gout = fam.simulate(world, plan)
        if gout is None:
            return None
        gcf = fam.simulate(cf_world, plan)
        cf_m = gcf.metrics if gcf is not None else None
        scored = answers.score_plan(fam, world, key, plan, sol.best, cf_m)
        if scored is None:
            return None
        if not (lo <= scored["points"] <= hi):
            return None
        hits.append({"plan": list(plan), "points": scored["points"], "metrics": dict(gout.metrics)})
    ref = answers.score(
        fam, world, key,
        answers.reference_text(world, key, core.Solver(fam, budget), best=sol.best),
        best=sol.best,
    )
    if not ref["passed"]:
        return None
    return {
        "optimal": dict(sol.best.metrics),
        "opt_plan": list(sol.best.plan),
        "n_opt": len(sol.optimal),
        "n_feasible": sol.n_feasible,
        "n_primary": sol.n_primary,
        "n_shared": sol.n_shared,
        "heuristics": hits,
        "cf": cf_sol.best.metrics[cf_q["metric"]],
    }
