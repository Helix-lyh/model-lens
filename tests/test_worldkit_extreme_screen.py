"""现有满分外卖题能不搜路线就断定有人必迟，极难筛应丢掉它。"""
from eval_bank_20260925.worldkit import extreme_screen as scr
from eval_bank_20260925.worldkit.families import delivery


def test_full_score_item_has_an_order_that_is_late_alone():
    forced = scr.solo_late_orders(delivery.extreme_world())
    assert "F" in forced
