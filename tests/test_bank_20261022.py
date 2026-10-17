"""20261022 题库：推理并列择支加难；编码/工程内容沿用，版本同步。"""
from eval_bank_20260925 import VERSION
from eval_bank_20260925.bank_manifest import ACTIVE_VERSION, ACTIVE_ITEMS, BANKS
from eval_bank_20260925 import reasoning_gen as gen
from eval_bank_20260925.next_reasoning import FROZEN


def test_active_version_aligned():
    assert ACTIVE_VERSION == VERSION == FROZEN["version"] == "20261022"
    assert {bank.version for bank in BANKS} == {"20261022"}
    assert gen.VERSION == "20261022"


def test_scoring_version_distinct():
    from eval_bank_20260925.bank_manifest import SCORING_VERSION, item_provenance
    assert SCORING_VERSION and SCORING_VERSION != ACTIVE_VERSION
    assert item_provenance("NX-09")["scoring_version"] == SCORING_VERSION


def test_active_items_count():
    assert len(ACTIVE_ITEMS) == 30
    assert len(FROZEN["items"]) == 10
