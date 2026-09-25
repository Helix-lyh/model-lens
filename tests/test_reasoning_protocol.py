import json
from copy import deepcopy

import pytest

from eval_bank_20260925.catalog import model_prompt
from eval_bank_20260925.score import golden, score_reasoning, summarize_repair
from eval_bank_20260925.runner import reference_source, score_coding
from eval_bank_20260925.score import Score


def test_nested_extra_keys_are_protocol_failures():
    data = deepcopy(golden("R-H-01"))
    data["base"]["extra"] = 1
    result = score_reasoning("R-H-01", json.dumps(data))
    assert result.status == "fail"
    assert result.protocol_ok is False
    assert result.points == 20


def test_bom_and_non_text_boundaries():
    text = json.dumps(golden("R-E-02"), ensure_ascii=False)
    assert score_reasoning("R-E-02", "\ufeff" + text).passed
    with pytest.raises(ValueError, match="response_not_text"):
        from eval_bank_20260925.score import parse_json
        parse_json(None)


def test_repair_rejects_any_round_after_first_pass():
    full = score_reasoning("R-E-02", json.dumps(golden("R-E-02")))
    missing = Score("R-E-02", None, "missing", "missing_fence", None, 20, None, None, [], False)
    with pytest.raises(ValueError, match="rounds_after_first_pass"):
        summarize_repair([full, missing])


def test_prompt_states_exact_nested_contract():
    prompt = model_prompt(next(i for i in __import__("eval_bank_20260925.catalog", fromlist=["ITEMS"]).ITEMS if i.id == "R-H-01"))
    assert "所有嵌套对象都必须且只能包含题面列出的字段" in prompt
