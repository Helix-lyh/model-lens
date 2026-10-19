"""题面渲染：题族头部 + 各模块条款（按 stage）+ 目标 + 问题 + 答案行约定。题面只由这些部件拼出。"""
from __future__ import annotations

from eval_bank_20260925.worldkit.answers import answer_format
from eval_bank_20260925.worldkit.core import Family

# 内部字段名与实现细节不得出现在题面中。
LEAK_TERMS = ("JSON", "Schema", "cf_", "flood", "closed-", "active_shock", "id 为", "mutex", "return_w",
              "check_at", "scope", "objective", "worldkit")

PLAN_HINT = "给出按目标最优的配送顺序。"


def question_text(family: Family, world: dict, q: dict) -> str:
    if q.get("text"):
        return q["text"]
    label = family.metrics[q["metric"]]
    if q.get("type") == "plan":
        return PLAN_HINT
    if q.get("cf"):
        return family.counterfactuals[q["cf"]].text(world) + f"按同一目标的最优顺序，{label}是多少？"
    return f"按目标最优的顺序，{label}是多少？"


def render_prompt(family: Family, world: dict) -> str:
    lines = [family.header(world)]
    mods = sorted(world["modules"], key=lambda k: (family.modules[k].stage, k))
    lines += [f"- {t}" for t in (family.modules[k].text(world["modules"][k], world) for k in mods) if t]
    lines.append("- " + family.objective_text(world))
    lines.append("问题：")
    lines += [f"问{i}：{question_text(family, world, q)}" for i, q in enumerate(world["questions"], 1)]
    lines.append(answer_format(len(world["questions"])))
    return "\n".join(lines)


def leaks(prompt: str) -> list[str]:
    return [t for t in LEAK_TERMS if t in prompt]
