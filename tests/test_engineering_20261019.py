"""20261019 工程题：计分依赖的行为写进题面；E-07 负数与库存不足按题面分码。"""
from eval_bank_20260925.engineering import ENGINEERING_SCENARIOS, reference_source, score_engineering


def _fence(src):
    return "```python\n" + src + "\n```"


def _points(item_id, src):
    r = score_engineering(_fence(src), item_id)
    return r["points"] if isinstance(r, dict) else r.points


def test_prompts_state_scored_behaviour():
    p = {k: v["prompt"] for k, v in ENGINEERING_SCENARIOS.items()}
    assert "临时锁定" in p["E-01"] and "10 次" in p["E-01"]
    assert "signature 为字符串 ok" in p["E-02"] and "floor(amount / 10)" in p["E-02"]
    assert "new 批次" in p["E-03"] and "returning 买家" in p["E-03"]
    assert "累计失败达到上限" in p["E-05"] and "2 到 6" in p["E-05"]
    assert "JSON 的 true" in p["E-06"]


def test_e07_reference_distinguishes_negative_from_short():
    ref = reference_source("E-07")
    assert _points("E-07", ref) == 20
    same = ref.replace('r=p("invalid", available=x["qty"])', 'r=p("rejected", available=x["qty"])')
    assert same != ref and _points("E-07", same) < 20
