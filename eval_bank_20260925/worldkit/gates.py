"""通用门禁：删除测试、联合度数、唯一性、反事实、触发、边界、读法敏感度、复核器对拍、无解冲突核。

所有门禁只依赖 core 的条件消融与求解，不为单个题族接线。门禁阈值读 world["gates"]：
  min_degree（默认 3）、min_boundary（默认 0）
"""
from __future__ import annotations

import itertools
from typing import Any

from eval_bank_20260925.worldkit.core import (
    INFEASIBLE, BudgetExceeded, Family, Solver, answers, conditions, main_questions, main_values,
    optimal_main_values,
)
from eval_bank_20260925.worldkit.oracles import oracle_for


def interacts(base: tuple, a: tuple, b: tuple, ab: tuple) -> bool:
    """A 与 B 联合承重：各自删除都改变主值，且同时删除与只删其一都不同。"""
    return a != base and b != base and ab != a and ab != b


def deletion_report(world: dict, solver: Solver, conds) -> list[dict]:
    base = main_values(world, solver(world))
    names = [q["name"] for q in main_questions(world)]
    out = []
    for c in conds:
        other = main_values(world, solver(c.apply(world)))
        changed = [n for n, x, y in zip(names, base, other) if x != y]
        out.append({"condition": c.name, "changed": changed, "ok": bool(changed)})
    return out


def degree_report(world: dict, solver: Solver, conds, min_degree: int) -> dict:
    base = main_values(world, solver(world))
    single = {c.name: main_values(world, solver(c.apply(world))) for c in conds}
    neighbors: dict[str, list[str]] = {c.name: [] for c in conds}
    for a, b in itertools.permutations(conds, 2):
        ab = main_values(world, solver(a.apply(b.apply(world))))
        if interacts(base, single[a.name], single[b.name], ab):
            neighbors[a.name].append(b.name)
    degree = {k: len(v) for k, v in neighbors.items()}
    return {"neighbors": neighbors, "degree": degree,
            "ok": bool(degree) and all(v >= min_degree for v in degree.values())}


def uniqueness_report(family: Family, world: dict, solver: Solver) -> dict:
    rep = {"main": len(optimal_main_values(world, solver(world))) == 1}
    for q in world["questions"]:
        if q.get("cf"):
            sol = solver(family.counterfactuals[q["cf"]].transform(world))
            vals = {INFEASIBLE} if sol.status != "ok" else {o.metrics[q["metric"]] for o in sol.optimal}
            rep[q["name"]] = len(vals) == 1
    return rep


def cf_report(world: dict, key: dict) -> dict:
    """反事实值必须与同指标的主值不同，否则反事实不起作用。"""
    mains = {q["metric"]: q["name"] for q in main_questions(world)}
    out = {}
    for q in world["questions"]:
        if q.get("cf") and q["metric"] in mains:
            out[q["name"]] = key[q["name"]] != key[mains[q["metric"]]]
    return out


def fired_report(family: Family, world: dict, solver: Solver) -> dict:
    """effect 类模块是否在最优方案的执行轨迹上实际触发。只报告不拒收：限制类规则常常通过
    「迫使最优方案绕开自己」承重（如 NX-18 的出餐时刻），承重本身由删除测试保证。"""
    sol = solver(world)
    if sol.status != "ok":
        return {"ok": True, "missing": [], "note": "infeasible"}
    bg = set(world.get("background", []))
    effects = [m for m in world["modules"] if m not in bg and family.modules[m].kind == "effect"]
    missing = [family.modules[m].title for m in effects if m not in sol.best.fired]
    return {"ok": not missing, "missing": missing}


def reading_report(family: Family, world: dict, solver: Solver) -> dict:
    base = main_values(world, solver(world))
    out = {}
    for name, fn in family.readings.items():
        alt = fn(world)
        if alt is not None:
            out[name] = main_values(alt, solver(alt)) != base
    return out


def oracle_report(family: Family, world: dict, solver: Solver, conds, key: dict) -> dict:
    """引擎与独立复核器在原世界、全部单删、全部双删上比较「最优方案主值集合」；原世界还比较全部问题。"""
    oracle = oracle_for(family.id)
    variants = [("base", world)] + [(c.name, c.apply(world)) for c in conds]
    variants += [(f"{a.name}+{b.name}", a.apply(b.apply(world))) for a, b in itertools.combinations(conds, 2)]
    mismatches = []
    for name, w in variants:
        mine = optimal_main_values(w, solver(w))
        theirs, _ = oracle.answers(w)
        if mine != theirs:
            mismatches.append({"variant": name, "engine": sorted(map(list, mine)), "oracle": sorted(map(list, theirs))})
    _, per_q = oracle.answers(world)
    for q in world["questions"]:
        if per_q[q["name"]] != {key[q["name"]]}:
            mismatches.append({"variant": "base", "question": q["name"], "engine": key[q["name"]],
                               "oracle": sorted(per_q[q["name"]], key=str)})
    return {"ok": not mismatches, "variants": len(variants), "mismatches": mismatches}


def conflict_report(world: dict, solver: Solver, conds) -> dict:
    """无解题：消融后变可解的条件构成必要集 C；放松其余条件后仍无解，则 C 本身构成冲突。
    取消、互斥、随时回站的消融会收紧可行集，放松时保留不动。"""
    core = [c for c in conds if solver(c.apply(world)).status == "ok"]
    rest = [c for c in conds if c not in core and c.relaxing]
    w = world
    for c in rest:
        w = c.apply(w)
    still = solver(w).status == "infeasible"
    return {"core": [c.name for c in core], "unique_minimal": still and len(core) >= 1,
            "ok": still and len(core) >= 2}


def run_gates(family: Family, world: dict, solver: Solver | None = None, fail_fast: bool = False) -> dict[str, Any]:
    """按代价从低到高跑门禁；fail_fast 时遇到第一个不通过即停（生成循环用），复核器对拍总在最后且不跳过。"""
    solver = solver or Solver(family)
    g = world.get("gates", {})
    rep: dict[str, Any] = {"reasons": [], "checks": {}}

    def check(name: str, ok: bool) -> bool:
        rep["checks"][name] = ok
        if not ok:
            rep["reasons"].append(name)
        return ok or not fail_fast

    try:
        base = solver(world)
        conds = conditions(family, world)
        key = answers(family, world, solver)
        rep["answer"] = key
        rep["search"] = {"plans": base.n_plans, "feasible": base.n_feasible, "optimal": len(base.optimal)}
        if base.status == "ok":
            rep["boundary"] = base.best.boundary
            rep["cf"] = cf_report(world, key)
            rep["uniqueness"] = uniqueness_report(family, world, solver)
            steps = [
                ("boundary", lambda: rep["boundary"] >= g.get("min_boundary", 0)),
                ("cf", lambda: all(rep["cf"].values())),
                ("uniqueness", lambda: all(rep["uniqueness"].values())),
                ("deletion", lambda: all(r["ok"] for r in rep.setdefault(
                    "deletion", deletion_report(world, solver, conds)))),
                ("degree", lambda: rep.setdefault(
                    "degree", degree_report(world, solver, conds, g.get("min_degree", 3)))["ok"]),
            ]
        else:
            steps = [("conflict", lambda: rep.setdefault("conflict", conflict_report(world, solver, conds))["ok"])]
        for name, fn in steps:
            if not check(name, fn()):
                break
        else:
            rep["oracle"] = oracle_report(family, world, solver, conds, key)
            check("oracle", rep["oracle"]["ok"])
            rep["readings"] = reading_report(family, world, solver)
            if base.status == "ok":
                rep["fired"] = fired_report(family, world, solver)
    except BudgetExceeded as exc:
        rep["reasons"].append(f"rejected:budget ({exc})")
    rep["accept"] = not rep["reasons"]
    return rep
