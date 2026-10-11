"""Executable 20261015 reasoning fixtures and mechanical scorers.

实例与答案键由 reasoning_gen.py（确定性种子 + 参考求解器）生成，冻结在 reasoning_20261015.json。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .reasoning_gen import schema_errors
from typing import Any

from .score import parse_json, strict_equal


@dataclass(frozen=True)
class ReasoningSpec:
    item_id: str
    title: str
    prompt: str
    answer: dict[str, Any]
    groups: tuple[tuple[str, int], ...]


def _spec(item_id, title, prompt, answer, groups):
    return ReasoningSpec(item_id, title, prompt.strip(), answer, groups)


# 分组与满分沿用 20261011，本轮不调整计分权重。
_GROUPS = {
    "NX-09": (("served", 10), ("waiting", 2), ("last_end", 4), ("infectious_rooms", 4)),
    "NX-10": (("assign", 12), ("rejected", 3), ("total_cost", 5)),
    "NX-11": (("locks", 8), ("loaded", 4), ("free", 4), ("rejected", 4)),
    "NX-12": (("route", 4), ("arrivals", 8), ("late", 4), ("total", 4)),
    "NX-13": (("flights", 10), ("cancelled", 3), ("duty", 5), ("last_end", 2)),
    "NX-14": (("schedule", 12), ("peak_cost", 4), ("finish_order", 4)),
    "NX-15": (("beds", 12), ("waiting", 2), ("disinfect_until", 4), ("emergency_wait", 2)),
    "NX-16": (("buy", 6), ("sold", 6), ("waste", 4), ("profit", 4)),
    "NX-17": (("path", 4), ("arrive", 3), ("cost", 3), ("alternatives", 8), ("reason", 2)),
    "NX-18": (("route", 4), ("arrivals", 8), ("late", 4), ("elevator_walk", 4)),
}

FROZEN_PATH = Path(__file__).with_name("reasoning_20261015.json")
FROZEN = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))


def _load_specs():
    out = []
    for row in FROZEN["items"]:
        item_id = row["item_id"]
        out.append(_spec(item_id, row["title"], row["prompt"], row["answer"], _GROUPS[item_id]))
    return tuple(out)


_SPECS = _load_specs()
SCHEMAS = {row["item_id"]: row["schema"] for row in FROZEN["items"]}

ITEMS = _SPECS
BY_ID = {item.item_id: item for item in ITEMS}


def reasoning_items():
    return ITEMS


def reasoning_group_maxes(item_id: str) -> tuple[tuple[str, int], ...]:
    """只返回 (分组名, 满分)。未知题目没有可补的分组，也不含题面。"""
    item = BY_ID.get(item_id) if isinstance(item_id, str) else None
    return () if item is None else item.groups


def render_reasoning_prompt(item_id: str) -> str:
    prompt = BY_ID[item_id].prompt
    return "你只能依据题面作答，只输出一个 JSON 对象，不要解释或增加字段。\n" + prompt


def _same_group(name: str, got: Any, expected: Any) -> bool:
    if name == "locks":
        return strict_equal(_lock_rows(got), _lock_rows(expected))
    return strict_equal(got, expected)


def _lock_rows(value: Any) -> Any:
    """订单、批次、数量。三元数组和对象是同一次锁定。"""
    if not isinstance(value, list):
        return value
    rows = []
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            rows.append([item[0], item[1], item[2]])
        elif isinstance(item, dict):
            order = item.get("order", item.get("id"))
            batch = item.get("batch")
            qty = item.get("qty")
            if order is None or batch is None or qty is None:
                return value
            rows.append([order, batch, qty])
        else:
            return value
    return rows


def score_reasoning(item_id: str, text: str) -> dict[str, Any]:
    item = BY_ID[item_id]
    try:
        data = parse_json(text)
    except (ValueError, TypeError, RecursionError) as exc:
        return {"status":"fail","reason_code":"format_error","passed":False,"points":0,"points_total":20,"score10":0.0,"protocol_ok":False,"groups":[],
                "schema_errors":[f"JSON 解析失败：{exc}"[:300]]}
    # 只做诊断，不改变计分：分数仍按分组逐项比较。
    schema_errs = schema_errors(SCHEMAS[item_id], data)
    if not isinstance(data, dict):
        data = {}
    protocol = set(data) == set(item.answer) and not schema_errs
    points = 0
    groups = []
    for name, maximum in item.groups:
        earned = maximum if _same_group(name, data.get(name), item.answer[name]) else 0
        points += earned
        groups.append({"name":name,"points":earned,"max":maximum})
    passed = protocol and points == 20
    return {"status":"pass" if passed else "fail","reason_code":"ok" if passed else ("content_mismatch" if protocol else "schema_mismatch"),"passed":passed,"points":points,"points_total":20,"score10":round(points / 2, 4),"protocol_ok":protocol,"groups":groups,"schema_errors":schema_errs[:20]}


def reference_answer(item_id: str) -> dict[str, Any]:
    return BY_ID[item_id].answer
