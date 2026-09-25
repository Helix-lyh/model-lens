import json

from eval_bank_20260925.engineering import (
    E01_PROMPT, ENGINEERING_SCENARIOS, login_reference, reference_source, score_engineering,
)


def fenced(source):
    return "```python\n" + source + "\n```"


def test_e01_reference_covers_all_obligations_without_prohibitions():
    result = score_engineering(fenced(reference_source()))
    assert result["passed"] is True, result
    assert len(result["obligations_covered"]) == 10
    assert result["prohibitions_triggered"] == []


def test_e01_is_black_box_and_not_an_exact_output_snapshot():
    assert "def solve(events)" in E01_PROMPT
    assert "账号隔离" not in E01_PROMPT
    assert "幂等行为" not in E01_PROMPT
    assert login_reference([{"op": "REGISTER", "user": "u", "password": "p", "now": 0}])[0]["ok"] is True
    assert ENGINEERING_SCENARIOS["E-01"]["status"] == "runnable"
    assert all(v["status"] == "runnable" for k, v in ENGINEERING_SCENARIOS.items())


def test_e01_positive_only_implementation_is_not_strict_pass():
    source = '''\
def solve(events):
    out = []
    for event in events:
        if event.get("op") == "LOGIN":
            out.append({"ok": True, "session": "fixed"})
        else:
            out.append({"ok": True})
    return out
'''
    result = score_engineering(fenced(source))
    assert result["passed"] is False
    assert result["obligations"]["covered"] < result["obligations_total"]


def test_e01_deny_all_cannot_earn_secret_or_security_obligations():
    result = score_engineering(fenced("def solve(events):\n    return [{'ok': False} for _ in events]"))
    assert "response_secret_not_echoed" not in result["obligations_covered"]
    assert result["obligations"]["gap"] > 0


def test_e01_result_has_separate_obligation_and_risk_ledgers():
    result = score_engineering(fenced(reference_source()))
    assert result["obligations"] == {"covered": 10, "total": 10, "gap": 0, "unobserved": 0}
    assert result["risk_debt"] == {"critical": 0, "high": 0, "medium": 0, "weighted_points": 0}
    assert "score10" not in result


def test_all_engineering_references_have_ten_positive_points():
    from eval_bank_20260925.engineering import reference_source, score_engineering
    for item_id in ("E-01", "E-02", "E-03", "E-04", "E-05", "E-06"):
        result = score_engineering(fenced(reference_source(item_id)), item_id)
        assert result["positive_points"] == 10, (item_id, result)
        assert result["negative_points"] == 0, (item_id, result)
        assert result["net_points"] == 10, (item_id, result)


def test_engineering_score_has_no_hidden_total_composition():
    from eval_bank_20260925.engineering import reference_source, score_engineering
    result = score_engineering(fenced(reference_source("E-02")), "E-02")
    assert result["obligations"] == {"covered": 10, "total": 10, "gap": 0, "unobserved": 0}
    assert result["risk_debt"]["weighted_points"] == 0
    assert "score10" not in result


def test_negative_implementations_create_deductions():
    from eval_bank_20260925.engineering import score_engineering
    bad = {
        "E-02": "def solve(events):\n    return [{'ok': True, 'status': 'PAID'} for _ in events]",
        "E-03": "def solve(events):\n    return [{'ok': True, 'available': -1} for _ in events]",
        "E-04": "def solve(events):\n    return [{'ok': True, 'found': True, 'content': 'private', 'amount': 0} for _ in events]",
        "E-05": "def solve(events):\n    return [{'ok': True, 'state': 'SUCCEEDED', 'run_count': 1} for _ in events]",
        "E-06": "def solve(events):\n    return [{'ok': True, 'value': 'a'} for _ in events]",
    }
    for item_id, source in bad.items():
        result = score_engineering(fenced(source), item_id)
        assert result["negative_points"] >= 1, (item_id, result)
        assert result["passed"] is False


def test_engineering_total_is_separate_sixty_point_ledger():
    from eval_bank_20260925.engineering import aggregate_engineering
    result = aggregate_engineering([
        {"positive_points": 10, "negative_points": 0, "obligations": {"total": 10}, "passed": True}
        for _ in range(6)
    ])
    assert result == {
        "questions": 6, "max_positive_points": 60, "positive_points": 60,
        "negative_points": 0, "net_points": 60, "strict_passed": 6,
    }
    assert "score10" not in result
