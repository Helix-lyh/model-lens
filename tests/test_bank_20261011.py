"""20261011 题库修订：题面消歧义、E-08 截止边界、版本号。"""
from __future__ import annotations

import eval_bank_20260925.plugins  # noqa: F401
from eval_bank_20260925 import VERSION
from eval_bank_20260925.bank_manifest import ACTIVE_VERSION, ACTIVE_ITEMS
from eval_bank_20260925.bank_registry import ITEMS
from eval_bank_20260925.engineering import reference_source
from eval_bank_20260925.engineering_next import CASES, PAIRS
from eval_bank_20260925.next_reasoning import BY_ID, reference_answer, score_reasoning
import json


def test_version_bumped_and_30_items():
    assert ACTIVE_VERSION == VERSION == "20261011"
    assert len(ACTIVE_ITEMS) == 30
    assert all(item in ITEMS for item in ACTIVE_ITEMS)


def test_reasoning_prompts_state_interpretations():
    nx10 = ITEMS.get("NX-10").prompt()
    assert "按 V1、V2、V3 的顺序依次分配" in nx10 and "end ≤ deadline" in nx10 and "主动等待" in nx10
    assert "`[order,batch,qty]`" in ITEMS.get("NX-11").prompt()
    assert "按 start、床号排序" in ITEMS.get("NX-15").prompt()
    nx13 = ITEMS.get("NX-13").prompt()
    assert "起飞时刻 09:00 不变" in nx13 and "end−start 之和" in nx13


def test_nx13_answer_matches_arrival_only_delay():
    answer = reference_answer("NX-13")
    f1 = answer["flights"][0]
    assert f1 == ["F1", "C1", 540, 670]  # 09:00 起飞不变，10:30+40 = 11:10 落地
    assert answer["duty"]["C1"] == 670 - 540


def test_reference_answers_still_full_score():
    for item_id in BY_ID:
        verdict = score_reasoning(item_id, json.dumps(reference_answer(item_id)))
        assert verdict["points"] == 20, item_id


def test_e07_prompt_defines_hidden_fields():
    prompt = ITEMS.get("E-07").prompt()
    for token in ("BATCH {batch,temp_min,temp_max,qty,temp}", "缺省 10", "SHIP 和 READ 可带 `available`"):
        assert token in prompt
    fields = {key for events in CASES["E-07"].values() for event in events if event["op"] == "BATCH" for key in event}
    assert fields <= {"op", "type", "batch", "temp_min", "temp_max", "qty", "temp"}


def test_e08_deadline_boundary_is_inclusive_and_stated():
    assert "`at ≤ deadline` 视为按时" in ITEMS.get("E-08").prompt()
    late = CASES["E-08"]["late"][1]
    ontime = CASES["E-08"]["ontime"][1]
    assert late["at"] > 10 and ontime["at"] == 10
    assert any(pair[0] == "evidence_boundary" for pair in PAIRS["E-08"])
    verdict = ITEMS.get("E-08").score("```python\n" + reference_source("E-08") + "\n```")
    assert verdict["positive_points"] == 20 and verdict["negative_points"] == 0
