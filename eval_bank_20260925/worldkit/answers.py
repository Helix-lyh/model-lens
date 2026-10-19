"""worldkit 答案类型、答案行解析与机械判分。

答案行：最后一个行首 `ANSWER:`，每问一段，英文或全角分号分隔。
- exact      整数，等于参考值
- tolerance  整数，落在 accept 给出的闭区间内（lo/hi 可写成相对参考值的偏移）
- plan       方案：订单号用短横线连接，中途回站写 W；判分器用题族规则重放方案，
             可行且满足 accept（optimal：目标键等于最优；或 metric 上限）才得分
- 无解       任一问的参考值为「无解」时，该问只判是否明确写了「无解」；
             整行只写一个「无解」视为每问都答无解
"""
from __future__ import annotations

import re
from typing import Any

from eval_bank_20260925.worldkit.core import INFEASIBLE, Family, Outcome, Solver, objective_key

POINTS_TOTAL = 20

_ANSWER_RE = re.compile(r"^\s*(?:[#>+\-]+\s*)*(?:final\s+)?answer\s*[:：=]\s*(.*)", re.IGNORECASE)
# 只排除紧贴 ASCII 字母数字的数字（如 L2、1.5）；「14分钟」「第14」照常解析
_INT_RE = re.compile(r"(?<![A-Za-z0-9_.])[-−]?\d+(?!\d|\.\d)")
_LABEL_RE = re.compile(r"^\s*(?:问\s*\d+|[qQ]\d+)\s*[:：=]?\s*")
_PLAN_SEP_RE = re.compile(r"\s*(?:->|→|-|—|–|−|‑|,|，|、)\s*|\s+")
_INFEASIBLE_LEAD = " \t:：*`'\"「『“（("


def answer_format(n: int) -> str:
    slots = "; ".join(f"<问{k}>" for k in range(1, n + 1))
    return (f"可以先写推理过程。最后一行必须是 `ANSWER: {slots}`：按问题顺序作答，用英文分号分隔；"
            "数值写整数，配送顺序写订单号并用短横线连接（中途回站写 W，例如 A-W-B-C）；"
            "若某一问已经规定了方案记号，按该问的记号书写；"
            "若不存在满足全部约束的方案，该问写「无解」。")


def answer_line(text: Any) -> str:
    if not isinstance(text, str):
        raise ValueError("response_not_text")
    hits = []
    for ln in text.replace("\r", "").split("\n"):
        clean = ln.replace("*", "").replace("`", "").replace("\ufeff", "")
        m = _ANSWER_RE.search(clean)
        if m:
            hits.append(m.group(1).strip())
    if not hits:
        raise ValueError("no_answer_line")
    return hits[-1]


def split_segments(line: str, n: int) -> list[str]:
    segs = [s.strip() for s in re.split(r"[;；]", line)]
    segs = [_LABEL_RE.sub("", s).strip().rstrip("。.") for s in segs if s.strip()]
    if len(segs) == 1 and n > 1 and says_infeasible(segs[0]):
        return [INFEASIBLE] * n
    if len(segs) != n:
        raise ValueError(f"expected_{n}_segments_got_{len(segs)}")
    return segs


def says_infeasible(seg: str) -> bool:
    """段首就是「无解」才算；「8（不是无解）」不算。"""
    s = seg.lstrip(_INFEASIBLE_LEAD)
    return s.startswith(INFEASIBLE) or s.lower().startswith(("no solution", "infeasible"))


def parse_int(seg: str) -> int:
    nums = _INT_RE.findall(seg)
    if len(nums) != 1:
        raise ValueError("not_single_integer")
    return int(nums[0].replace("−", "-"))


def parse_plan(seg: str) -> tuple[str, ...]:
    parts = [p.strip().upper() for p in _PLAN_SEP_RE.split(seg.strip()) if p.strip()]
    if not parts or not all(re.fullmatch(r"[A-Z][A-Z0-9]*", p) for p in parts):
        raise ValueError("bad_plan")
    return tuple(parts)


def _bound(spec: Any, ref: int) -> int:
    if isinstance(spec, dict):
        return ref + spec["delta"]
    return spec


def _drop_forced_returns(live: dict, plan: tuple[str, ...]) -> tuple[str, ...] | None:
    """不允许随时回站时，模型把「送满上限后的强制回站」写成 W 也算同一方案；其余 W 不允许。"""
    mods = live["modules"]
    if "return_w" in mods:
        return plan
    cap = mods["carry"]["max"] if "carry" in mods else None
    out, carry = [], 0
    for step in plan:
        if step != "W":
            if cap is not None and carry >= cap:
                carry = 0
            out.append(step)
            carry += 1
            continue
        if cap is None or carry < cap:
            return None
        carry = 0
    return tuple(out)


def judge(
    family: Family,
    world: dict,
    q: dict,
    ref: Any,
    seg: str,
    solver: Solver,
    best: Outcome | None = None,
) -> tuple[bool, str]:
    """返回 (是否得分, 说明)。"""
    if ref == INFEASIBLE:
        return says_infeasible(seg), "expect_infeasible"
    if says_infeasible(seg):
        return False, "said_infeasible"
    kind = q.get("type", "exact")
    if kind == "exact":
        return parse_int(seg) == ref, "exact"
    if kind == "tolerance":
        v = parse_int(seg)
        acc = q["accept"]
        return _bound(acc["lo"], ref) <= v <= _bound(acc["hi"], ref), "tolerance"
    if kind == "plan":
        plan = parse_plan(seg)
        live = family.effective(world)
        normalizer = getattr(family, "normalize_plan", None)
        if normalizer is not None:
            plan = normalizer(plan)
            if plan is None:
                return False, "bad_plan"
        else:
            if sorted(p for p in plan if p != "W") != family.active_orders(live):
                return False, "plan_orders_mismatch"
            if plan[0] == "W" or plan[-1] == "W" or any(a == b == "W" for a, b in zip(plan, plan[1:])):
                return False, "plan_bad_return"
            plan = _drop_forced_returns(live, plan)
            if plan is None:
                return False, "plan_return_not_allowed"
        out = family.simulate(live, plan)
        if out is None:
            return False, "plan_infeasible"
        acc = q.get("accept", "optimal")
        if acc == "optimal":
            ref_best = best if best is not None else solver(world).best
            return objective_key(world, out) == objective_key(world, ref_best), "plan_optimal"
        return out.metrics[acc["metric"]] <= _bound(acc["max"], ref), "plan_threshold"
    raise ValueError(f"unknown question type {kind}")


def score(
    family: Family,
    world: dict,
    key: dict[str, Any],
    text: Any,
    solver: Solver | None = None,
    best: Outcome | None = None,
) -> dict[str, Any]:
    """key 为冻结的参考答案 {问题名: 值}；plan 题的参考值是最优方案对应的 accept 指标值。"""
    solver = solver or Solver(family)
    qs = world["questions"]
    groups = [{"name": q["name"], "points": 0, "max": q["points"]} for q in qs]
    try:
        segs = split_segments(answer_line(text), len(qs))
    except ValueError as exc:
        return {"status": "fail", "reason_code": "format_error", "passed": False, "points": 0,
                "points_total": POINTS_TOTAL, "score10": 0.0, "protocol_ok": False, "groups": groups,
                "schema_errors": [f"答案解析失败：{exc}"[:300]]}
    errors = []
    for g, q, seg in zip(groups, qs, segs):
        try:
            ok, why = judge(family, world, q, key[q["name"]], seg, solver, best)
        except ValueError as exc:
            ok, why = False, str(exc)
        g["got"] = seg
        g["why"] = why
        if ok:
            g["points"] = q["points"]
        else:
            errors.append(f"{q['name']}: {why}")
    points = sum(g["points"] for g in groups)
    passed = points == POINTS_TOTAL
    return {"status": "pass" if passed else "fail", "reason_code": "ok" if passed else "content_mismatch",
            "passed": passed, "points": points, "points_total": POINTS_TOTAL, "score10": round(points / 2, 1),
            "protocol_ok": True, "groups": groups, "schema_errors": errors}


def reference_segment(
    q: dict, ref: Any, world: dict, solver: Solver, best: Outcome | None = None
) -> str:
    if ref == INFEASIBLE:
        return INFEASIBLE
    if q.get("type") == "plan":
        if best is not None:
            return "-".join(best.plan)
        return "-".join(solver(world).best.plan)
    return str(ref)


def reference_text(
    world: dict, key: dict[str, Any], solver: Solver, best: Outcome | None = None
) -> str:
    return "ANSWER: " + "; ".join(
        reference_segment(q, key[q["name"]], world, solver, best) for q in world["questions"]
    )


def replay_text(world: dict, plan: tuple, metrics: dict[str, int], cf_metrics: dict[str, int] | None = None) -> str:
    """用某份方案自己的整数拼答案行：模型交出自洽但非最优答卷时就是这个形状。"""
    parts = []
    for q in world["questions"]:
        if q.get("type") == "plan":
            parts.append("-".join(str(p) for p in plan))
        elif q.get("cf"):
            parts.append(str((cf_metrics or metrics)[q["metric"]]))
        else:
            parts.append(str(metrics[q["metric"]]))
    return "ANSWER: " + "; ".join(parts)


def score_plan(
    family: Family,
    world: dict,
    key: dict[str, Any],
    plan: tuple,
    best: Outcome | None,
    cf_metrics: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    """自洽重放：方案按题族模拟，整数用该方案自己的数（反事实问用 cf_metrics）。"""
    live = family.effective(world)
    out = family.simulate(live, plan)
    if out is None:
        return None
    return score(family, world, key, replay_text(world, plan, out.metrics, cf_metrics), best=best)
