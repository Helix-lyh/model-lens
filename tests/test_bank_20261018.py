"""20261018 题库：推理题扩相互关联约束（删除测试）；编码/工程沿用；答案收敛。"""
from __future__ import annotations

import eval_bank_20260925.plugins  # noqa: F401
from eval_bank_20260925 import VERSION
from eval_bank_20260925.bank_manifest import ACTIVE_VERSION, ACTIVE_ITEMS, BANKS
from eval_bank_20260925.bank_registry import ITEMS
from eval_bank_20260925.engineering import reference_source
from eval_bank_20260925.engineering_next import CASES, PAIRS
from eval_bank_20260925.next_reasoning import FROZEN


def test_version_bumped_and_30_items():
    assert ACTIVE_VERSION == VERSION == FROZEN["version"] == "20261018"
    assert {bank.version for bank in BANKS} == {"20261018"}
    assert len(ACTIVE_ITEMS) == 30
    assert all(item in ITEMS for item in ACTIVE_ITEMS)


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


def test_scoring_version_is_separate_and_in_provenance_and_resume_keys():
    import importlib.util
    from pathlib import Path
    from eval_bank_20260925.bank_manifest import SCORING_VERSION, item_provenance
    assert SCORING_VERSION and SCORING_VERSION != ACTIVE_VERSION
    assert item_provenance("NX-09")["scoring_version"] == SCORING_VERSION
    path = Path(__file__).resolve().parents[1] / "cursor_workspace" / "build_scripts" / "run_eval_20260925.py"
    text = path.read_text(encoding="utf-8")
    assert '"scoring_version"' in text.split("RESUME_KEYS = ", 1)[1].split("\n", 1)[0]
    assert '"scoring_version": SCORING_VERSION' in text
