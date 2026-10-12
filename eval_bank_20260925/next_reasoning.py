"""Executable 20261017 reasoning fixtures and mechanical scorers.

实例与答案键由 reasoning_gen.py（确定性种子 + 参考求解器）生成，冻结在 reasoning_20261017.json。
题面开放、不规定数据结构；每题只判 2 个主数值（+ 含互斥突发的题 1 个反事实数值）。
答案格式只保留最小约定：最后一个 `ANSWER:` 行按问题顺序给整数；解析对代码块、Markdown 修饰、前后说明宽容。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReasoningSpec:
    item_id: str
    title: str
    prompt: str
    answer: dict[str, Any]
    groups: tuple[tuple[str, int], ...]


FROZEN_PATH = Path(__file__).with_name("reasoning_20261017.json")
FROZEN = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))


def _load_specs():
    out = []
    for row in FROZEN["items"]:
        groups = tuple((k["name"], k["points"]) for k in row["keys"])
        out.append(ReasoningSpec(row["item_id"], row["title"], row["prompt"].strip(), row["answer"], groups))
    return tuple(out)


ITEMS = _load_specs()
BY_ID = {item.item_id: item for item in ITEMS}
_GROUPS = {item.item_id: item.groups for item in ITEMS}


def reasoning_items():
    return ITEMS


def reasoning_group_maxes(item_id: str) -> tuple[tuple[str, int], ...]:
    """只返回 (分组名, 满分)。未知题目没有可补的分组，也不含题面。"""
    item = BY_ID.get(item_id) if isinstance(item_id, str) else None
    return () if item is None else item.groups


def render_reasoning_prompt(item_id: str) -> str:
    return "只依据题面推理作答。\n" + BY_ID[item_id].prompt


_ANSWER_RE = re.compile(r"answer\s*[:：=]\s*(.*)", re.IGNORECASE)
_INT_RE = re.compile(r"(?<![\w.])[-−]?\d+(?![\w.])")


def parse_answer(text: Any, n: int) -> list[int]:
    """取最后一个 `ANSWER:` 行中的整数，恰好 n 个。

    宽容：任意代码块围栏、Markdown 粗体/反引号、全角冒号、前后有说明文字、`问1=…` 之类的标签；
    不接受：缺少 ANSWER 行、数值个数不符、小数。"""
    if not isinstance(text, str):
        raise ValueError("response_not_text")
    lines = [ln for ln in text.replace("\r", "").split("\n")]
    hits = []
    for ln in lines:
        clean = ln.replace("*", "").replace("`", "").replace("\ufeff", "")
        m = _ANSWER_RE.search(clean)
        if m:
            hits.append(m.group(1))
    if not hits:
        raise ValueError("no_answer_line")
    body = re.sub(r"问\s*\d+\s*[:：=]?", " ", hits[-1])
    body = re.sub(r"[qQ]\d+\s*[:：=]", " ", body)
    nums = [int(x.replace("−", "-")) for x in _INT_RE.findall(body)]
    if len(nums) != n:
        raise ValueError(f"expected_{n}_integers_got_{len(nums)}")
    return nums


def score_reasoning(item_id: str, text: str) -> dict[str, Any]:
    item = BY_ID[item_id]
    names = [name for name, _ in item.groups]
    try:
        got = parse_answer(text, len(names))
    except ValueError as exc:
        return {"status": "fail", "reason_code": "format_error", "passed": False, "points": 0, "points_total": 20,
                "score10": 0.0, "protocol_ok": False,
                "groups": [{"name": n, "points": 0, "max": m} for n, m in item.groups],
                "schema_errors": [f"答案解析失败：{exc}"[:300]]}
    points = 0
    groups = []
    for (name, maximum), value in zip(item.groups, got):
        earned = maximum if value == item.answer[name] else 0
        points += earned
        groups.append({"name": name, "points": earned, "max": maximum, "got": value})
    passed = points == 20
    return {"status": "pass" if passed else "fail", "reason_code": "ok" if passed else "content_mismatch",
            "passed": passed, "points": points, "points_total": 20, "score10": round(points / 2, 1),
            "protocol_ok": True, "groups": groups, "schema_errors": []}


def reference_answer(item_id: str) -> dict[str, Any]:
    return BY_ID[item_id].answer


def reference_text(item_id: str) -> str:
    return "ANSWER: " + ", ".join(str(v) for v in BY_ID[item_id].answer.values())
