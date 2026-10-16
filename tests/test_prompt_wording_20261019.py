"""20261019 题面措辞：不出现题号、评测文件名、点明题型的前缀和「答案」字样的盐值。"""
import re

from eval_bank_20260925.challenge import salt_prompt
from eval_bank_20260925.engineering import ENGINEERING_SCENARIOS
from eval_bank_20260925.next_reasoning import render_reasoning_prompt, ITEMS


def test_salt_has_no_answer_word():
    out = salt_prompt("题", "abc")
    assert "答案" not in out and "abc" in out


def test_engineering_prompts_have_no_item_id_or_harness_file():
    for item, row in ENGINEERING_SCENARIOS.items():
        text = row["prompt"]
        assert not re.search(r"E-\d\d", text), item
        assert "solution.py" not in text and "工程题" not in text and "评测" not in text, item


def test_reasoning_prompt_has_no_genre_prefix():
    for it in ITEMS:
        assert not render_reasoning_prompt(it.item_id).startswith("只依据题面")
