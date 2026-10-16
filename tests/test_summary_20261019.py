"""20261019 汇总口径：pass@k 与固定分母同一批样本；截断时分组累计与固定分母一致。"""
from eval_bank_20260925.evaluation import pass_at_k, summarize


def _row(sample, status, **kw):
    base = {"experiment_id": "x", "channel": "c", "model": "m", "bank_id": "b", "bank_version": "v",
            "item": "NX-09", "lang": None, "sample": sample, "status": status,
            "passed": True if status == "pass" else (False if status == "fail" else None)}
    base.update(kw)
    return base


def test_pass_at_k_counts_truncated_and_request_errors_as_samples():
    rows = [
        _row(0, "pass", points=20, points_total=20, score10=10, groups=[{"name": "last_end", "points": 12, "max": 12}, {"name": "waiting_n", "points": 8, "max": 8}]),
        _row(1, "error", reason_code="response_truncated"),
        _row(2, "error", reason_code="request_error"),
    ]
    assert pass_at_k(rows, 1)[0] == round(1 / 3, 4)
    assert pass_at_k(rows, 3)[0] == 1.0  # 3 次里至少 1 次通过
    s = summarize(rows, pass_k=3)
    assert s["points_total"] == 60 and s["score_percent_total"] == 33.3
    totals = {g["name"]: (g["points"], g["max"]) for g in s["group_totals"]}
    assert totals == {"last_end": (12, 36), "waiting_n": (8, 24)}
