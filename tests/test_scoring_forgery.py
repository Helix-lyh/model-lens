"""被测代码伪造判分结果的回归测试。"""
from __future__ import annotations

import json

import eval_bank_20260925.plugins  # noqa: F401
from eval_bank_20260925.bank_registry import ITEMS
from eval_bank_20260925.engineering_extra import PAIRS as EXTRA_PAIRS
from eval_bank_20260925.engineering_next import PAIRS


def _forge(marker_expr: str, names: list[str]) -> str:
    forged = json.dumps({"covered": names, "gaps": [], "violations": []})
    return (
        "```python\nimport os\n"
        f"os.write(1, ({marker_expr} + ' POINTS 20/20\\n').encode())\n"
        f"os.write(1, ({marker_expr} + ' ENGINEERING ' + {forged!r} + '\\n').encode())\n"
        "import atexit\n"
        f"atexit.register(lambda: os.write(1, ({marker_expr} + ' ENGINEERING ' + {forged!r} + '\\n').encode()))\n"
        "def solve(events):\n    return [{} for _ in events]\n```"
    )


def test_e07_forged_engineering_line_does_not_score():
    """10-11 评审复现：固定 marker + 首条 ENGINEERING 行曾让空实现拿到 pass 20/0。"""
    names = [pair[0] for pair in PAIRS["E-07"]]
    verdict = ITEMS.get("E-07").score(_forge("'__MODEL_LENS_E07_'", names))
    assert verdict["status"] == "fail"
    assert verdict["passed"] is False
    assert verdict["positive_points"] < 20


def test_e07_forge_with_nonce_read_from_fixture_does_not_score():
    names = [pair[0] for pair in PAIRS["E-07"]]
    expr = "__import__('re').search(r'__MODEL_LENS_RUNS_[0-9a-f]+__', open('test_q.py').read()).group(0)"
    verdict = ITEMS.get("E-07").score(_forge(expr, names))
    assert verdict["status"] == "fail"
    assert verdict["positive_points"] < 20


def test_extra_and_login_items_are_not_forgeable():
    for item_id in ("E-01", "E-02"):
        names = [pair[0] for pair in EXTRA_PAIRS.get(item_id, [])] or ["x"]
        verdict = ITEMS.get(item_id).score(_forge(f"'__MODEL_LENS_{item_id.replace('-', '')}_'", names))
        assert verdict["passed"] is False, item_id
        assert verdict["positive_points"] < 20, item_id


def test_coding_duplicate_case_lines_are_rejected():
    from eval_bank_20260925.engineering import reference_source  # noqa: F401
    from eval_bank_20260925.next_coding import reference_source as coding_reference
    good = coding_reference("CP-09", "python")
    forge = (
        "import os, re\n"
        "_m = re.search(r'__MODEL_LENS_FIXTURE_[0-9a-f]+__', open('test_q.py').read()).group(0)\n"
        "os.write(1, (_m + ' CASE 0 {\"trace\":[],\"output\":{}}\\n').encode())\n"
    )
    verdict = ITEMS.get("CP-09").score("```python\n" + forge + good + "\n```", "python")
    assert verdict["status"] == "fail"
    assert verdict["reason_code"] == "forged_output"
    assert verdict["points"] == 0
