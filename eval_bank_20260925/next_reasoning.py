"""Executable 20261016 reasoning fixtures and mechanical scorers.

实例与答案键由 reasoning_gen.py（确定性种子 + 参考求解器）生成，冻结在 reasoning_20261016.json。
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


# 20261016b：为含反事实的题目把 cf_* / active_shock 纳入分组计分（每题总分仍 20）。
# 分配原则：主结构字段保留过半；cf 标量 4 分（难猜）；active_shock 2 分（短 id，权重低于 cf）；
# 其余从原主字段按比例下调。NX-09/14/16 无反事实字段，权重不变。
_GROUPS = {
    "NX-09": (("served", 10), ("waiting", 2), ("last_end", 4), ("infectious_rooms", 4)),
    # was 12+3+5 → 主字段 14，cf+shock 6
    "NX-10": (("assign", 8), ("rejected", 2), ("total_cost", 4), ("cf_cost", 4), ("active_shock", 2)),
    # was 8+4+4+4 → 主 14，cf+shock 6
    "NX-11": (("locks", 6), ("loaded", 3), ("free", 3), ("rejected", 2), ("cf_free_sum", 4), ("active_shock", 2)),
    # was 4+8+4+4 → 主 14，cf+shock 6
    "NX-12": (("route", 3), ("arrivals", 6), ("late", 3), ("total", 2), ("cf_total", 4), ("active_shock", 2)),
    # was 10+3+5+2 → 主 14，cf+shock 6
    "NX-13": (("flights", 7), ("cancelled", 2), ("duty", 4), ("last_end", 1), ("cf_cancelled_n", 4), ("active_shock", 2)),
    "NX-14": (("schedule", 12), ("peak_cost", 4), ("finish_order", 4)),
    # was 12+2+4+2 → 主 14，cf+shock 6
    "NX-15": (("beds", 8), ("waiting", 2), ("disinfect_until", 3), ("emergency_wait", 1), ("cf_emergency_wait", 4), ("active_shock", 2)),
    "NX-16": (("buy", 6), ("sold", 6), ("waste", 4), ("profit", 4)),
    # was 4+3+3+8+2 → 主 14，cf+shock 6
    "NX-17": (("path", 3), ("arrive", 2), ("cost", 2), ("alternatives", 6), ("reason", 1), ("cf_arrive", 4), ("active_shock", 2)),
    # was 4+8+4+4 → 主 14，cf+shock 6
    "NX-18": (("route", 3), ("arrivals", 5), ("late", 3), ("elevator_walk", 3), ("cf_elevator_walk", 4), ("active_shock", 2)),
}

FROZEN_PATH = Path(__file__).with_name("reasoning_20261016.json")
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
