"""20261008 原推理冻结副本（NX08 跑次用）。"""
from __future__ import annotations

import json

from eval_bank_20260925 import next_reasoning_20261008 as orig


def test_reference_scores_full():
    for item in orig.ITEMS:
        text = json.dumps(item.answer, ensure_ascii=False)
        full = orig.score_reasoning(item.item_id, text)
        assert full["passed"] and full["points"] == 20, (item.item_id, full)


def test_nx09_fifth_patient_shifts_infectious_room():
    ans = orig.BY_ID["NX-09"].answer
    assert ans["last_end"] == 21
    assert ans["infectious_rooms"] == ["R1", "R2"]
    assert ["E", "R1", 5, 13] in ans["served"]
    assert ans["waiting"] == []


def test_nx12_deadlines_make_all_late():
    ans = orig.BY_ID["NX-12"].answer
    assert ans["late"] == ["A", "B", "C"]
    assert ans["total"] == 19
    assert "deadline 5" in orig.BY_ID["NX-12"].prompt
    assert "`late` 按 id 排序" in orig.BY_ID["NX-12"].prompt


def test_nx14_peak_car_splits_schedule_from_peak():
    ans = orig.BY_ID["NX-14"].answer
    assert ans["peak_cost"] == 12
    assert ans["finish_order"] == ["A", "D", "B", "C"]
    assert any(row[0] == "D" for row in ans["schedule"])


def test_nx16_four_day_hot_close_unique():
    ans = orig.BY_ID["NX-16"].answer
    assert ans == {"buy": [8, 0, 8, 0], "sold": [4, 4, 4, 4], "waste": [0, 0, 0, 0], "profit": 64}
    assert "四天" in orig.BY_ID["NX-16"].prompt
