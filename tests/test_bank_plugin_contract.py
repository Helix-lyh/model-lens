from eval_bank_20260925.bank_adapters import render_item_prompt, score_item_with_adapter
from eval_bank_20260925.bank_manifest import ACTIVE_ITEMS, PROGRAMMING_ACTIVE
from eval_bank_20260925.bank_registry import ITEMS


def test_20261008_active_items_are_registry_plugins():
    assert len(PROGRAMMING_ACTIVE) == 10
    assert len(ACTIVE_ITEMS) == 30
    assert ACTIVE_ITEMS[:10] == PROGRAMMING_ACTIVE
    plugin = ITEMS.get("CP-09")
    assert dict(plugin.runtime_profiles) == {}
    prompt = render_item_prompt(type("Q", (), {"id": "CP-09"})())
    assert "def describe()" in prompt
    assert "python-dateutil" not in prompt


def test_plugin_scoring_dispatches_without_adapter_branch():
    result = score_item_with_adapter(type("Q", (), {"id": "CP-09"})(), "```python\ndef solve(data): return {}\n```")
    assert result["status"] in {"fail", "error", "missing"}


def test_all_next_items_are_explicitly_registered_and_pending_is_unjudged():
    assert {item.item_id for item in ITEMS.items("coding")} == set(PROGRAMMING_ACTIVE)
    assert {item.item_id for item in ITEMS.items("engineering")} == set(__import__('eval_bank_20260925.bank_manifest', fromlist=['ENGINEERING_ACTIVE']).ENGINEERING_ACTIVE)
    assert {item.item_id for item in ITEMS.items("reasoning")} == set(__import__('eval_bank_20260925.bank_manifest', fromlist=['REASONING_ACTIVE']).REASONING_ACTIVE)
