import json

from eval_bank_20260925.engineering import (
    E01_PROMPT, ENGINEERING_SCENARIOS, ENGINEERING_VERSION, login_reference, reference_source, score_engineering,
)


def test_engineering_v1_is_frozen():
    assert ENGINEERING_VERSION == "v3.3"


def fenced(source):
    return "```python\n" + source + "\n```"


def test_e01_reference_covers_all_obligations_without_prohibitions():
    result = score_engineering(fenced(reference_source()))
    assert result["passed"] is True, result
    assert len(result["obligations_covered"]) == 20
    assert result["positive_points"] == 20
    assert result["prohibitions_total"] == 20
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
    assert "no_secret" not in result["obligations_covered"] or result["obligations"]["gap"] > 0
    assert result["obligations"]["gap"] > 0


def test_e01_result_has_separate_obligation_and_risk_ledgers():
    result = score_engineering(fenced(reference_source()))
    assert result["obligations"] == {"covered": 20, "total": 20, "gap": 0, "unobserved": 0}
    assert result["risk_debt"] == {"critical": 0, "high": 0, "medium": 0, "weighted_points": 0}
    assert "score10" not in result


def test_all_engineering_references_have_ten_positive_points():
    from eval_bank_20260925.engineering import reference_source, score_engineering
    for item_id in ("E-01", "E-02", "E-03", "E-04", "E-05", "E-06"):
        result = score_engineering(fenced(reference_source(item_id)), item_id)
        assert result["positive_points"] == 20, (item_id, result)
        assert result["negative_points"] == 0, (item_id, result)
        assert result["net_points"] == 20, (item_id, result)
        assert result["prohibitions_total"] == 20


def test_engineering_score_has_no_hidden_total_composition():
    from eval_bank_20260925.engineering import reference_source, score_engineering
    result = score_engineering(fenced(reference_source("E-02")), "E-02")
    assert result["obligations"] == {"covered": 20, "total": 20, "gap": 0, "unobserved": 0}
    assert result["risk_debt"]["weighted_points"] == 0
    assert "score10" not in result


def test_negative_implementations_create_deductions():
    from eval_bank_20260925.engineering import ENGINEERING_VERSION, score_engineering
    bad = {
        "E-02": "def solve(events):\n    return [{'code':'X','reason':'X'} for e in events]",
        "E-03": "def solve(events):\n    return [{'code':'X','reason':'X','available':-1} for e in events]",
        "E-04": "def solve(events):\n    return [{'code':'X','reason':'private','amount':0} for e in events]",
        "E-05": "def solve(events):\n    return [{'code':'X','reason':'X'} for e in events]",
        "E-06": "def solve(events):\n    return [{'code':'X','reason':'X','value':'a'} for e in events]",
    }
    for item_id, source in bad.items():
        result = score_engineering(fenced(source), item_id)
        assert 1 <= result["negative_points"] <= 20, (item_id, result)
        assert result["passed"] is False


def test_same_error_with_different_event_ids_is_not_disclosure():
    source = '''
def solve(events):
    out = []
    for event in events:
        op = event.get("op") or event.get("type")
        if op == "REGISTER":
            out.append({"id": event.get("id"), "ok": True})
        elif op == "LOGIN":
            out.append({"id": event.get("id"), "ok": False, "code": "LOGIN_FAILED", "reason": "LOGIN_FAILED"})
        else:
            out.append({"id": event.get("id"), "ok": False, "error": "INVALID_EVENT"})
    return out
'''
    result = score_engineering(fenced(source))
    assert "deduct_bad_vs_unknown" in result["prohibitions_triggered"]
    assert "bad_vs_unknown" not in result["obligations_covered"]


def test_empty_engineering_output_is_a_gap_not_a_risk():
    empty = "def solve(events):\n    return []"
    for item_id in ("E-03", "E-04", "E-05", "E-06"):
        result = score_engineering(fenced(empty), item_id)
        assert result["negative_points"] == 0, (item_id, result)
        assert result["positive_points"] == 0, (item_id, result)
        assert result["net_points"] == 0


def test_reason_relation_treats_code_reason_as_one_observable_pair():
    from eval_bank_20260925.engineering_extra import judge_item

    runs = {
        "left": [{"code": "A", "reason": "left"}],
        "right": [{"code": "A", "reason": "right"}],
    }
    module = __import__("eval_bank_20260925.engineering_extra", fromlist=["PAIRS"])
    original = module.PAIRS["E-02"]
    try:
        module.PAIRS["E-02"] = [["one", ["left", 0, "code"], ["right", 0, "code"], False, "eq"]]
        verdict = judge_item("E-02", runs)
    finally:
        module.PAIRS["E-02"] = original
    assert verdict["covered"] == ["one"]
    assert verdict["violations"] == []

    try:
        module.PAIRS["E-02"] = [["one", ["left", 0, "code"], ["right", 0, "code"], True, "eq"]]
        verdict = judge_item("E-02", runs)
    finally:
        module.PAIRS["E-02"] = original
    assert verdict["covered"] == []
    assert verdict["violations"] == ["deduct_one"]


def test_engineering_summary_excludes_generic_pass_at_k():
    from cursor_workspace.build_scripts import run_eval_20260925 as run_eval

    rows = [{
        "channel": "stub", "item": "E-01", "status": "fail", "passed": False,
        "positive_points": 14, "negative_points": 6, "net_points": 8,
        "obligations": {"covered": 14, "total": 20},
    }]
    summary = run_eval.summarize(rows, ["stub"])["stub"]
    assert "overall" not in summary
    assert summary["engineering"]["judged"] == 1
    assert summary["engineering"]["net_points"] == 8
    assert summary["engineering"]["pass_at_1"] == 0.0
    assert summary["engineering"]["pass_at_k"] == 0.0
    assert summary["engineering"]["net_points"] == 8


def test_wish_prompts_do_not_list_scored_points():
    from eval_bank_20260925.engineering_extra import CASES
    banned = ("幂等", "隔离", "超卖", "106", "保全", "不要写程序", "场景1从空状态开始", "REJECTED_")
    for item_id in ("E-01", "E-02", "E-03", "E-04", "E-05", "E-06"):
        prompt = ENGINEERING_SCENARIOS[item_id]["prompt"]
        assert "def solve(events)" in prompt
        for word in banned:
            assert word not in prompt, (item_id, word)
    for item_id, cases in CASES.items():
        from eval_bank_20260925.engineering_extra import PAIRS
        assert len(PAIRS[item_id]) == 20
        assert len({pair[0] for pair in PAIRS[item_id]}) == 20


def test_e07_to_e10_prompts_keep_the_wish_and_drop_the_score_key():
    import re

    from eval_bank_20260925.next_questions import DOCS, _sections

    sections = _sections(DOCS["engineering"], "E")
    for item_id in ("E-07", "E-08", "E-09", "E-10"):
        body = sections[item_id][1]
        match = re.search(r"\*\*题面全文。\*\*\s*(.+?)(?:\n\*\*|\Z)", body, re.S)
        assert match is not None, item_id
        wish = match.group(1).strip()
        prompt = ENGINEERING_SCENARIOS[item_id]["prompt"]
        assert "做一个生产级别可用的" in wish
        assert prompt == wish
        assert "可机械判分" not in prompt
        assert "参考行为" not in prompt
    assert ENGINEERING_SCENARIOS["E-01"]["prompt"] == E01_PROMPT


def test_engineering_total_is_separate_sixty_point_ledger():
    from eval_bank_20260925.engineering import aggregate_engineering
    result = aggregate_engineering([
        {"positive_points": 20, "negative_points": 0, "obligations": {"total": 20}, "passed": True}
        for _ in range(6)
    ])
    assert result == {
        "questions": 6, "max_positive_points": 120, "positive_points": 120,
        "negative_points": 0, "net_points": 120, "strict_passed": 6,
    }
    assert "score10" not in result


def test_e08_read_available_is_unsubmitted_until_submit():
    from eval_bank_20260925.engineering import reference_source, score_engineering
    from eval_bank_20260925.engineering_next import PAIRS

    relation = next(row for row in PAIRS["E-08"] if row[0] == "submit_count")
    assert relation[1:] == [["submit", 3, "available"], ["lit", 0], True, "eq"]

    source = reference_source("E-08")
    namespace = {}
    exec(source, namespace)
    rows = namespace["solve"]([
        {"op": "CASE", "case": "c", "order": "o", "deadline": 10},
        {"op": "READ", "case": "c"},
        {"op": "EVIDENCE", "case": "c", "evidence_id": "e1", "at": 1, "request_id": "r1"},
        {"op": "READ", "case": "c"},
        {"op": "EVIDENCE", "case": "c", "evidence_id": "e2", "at": 2, "request_id": "r2"},
        {"op": "READ", "case": "c"},
        {"op": "SUBMIT", "case": "c", "at": 10, "request_id": "s"},
        {"op": "READ", "case": "c"},
    ])
    assert [rows[i]["available"] for i in (1, 3, 5, 7)] == [0, 1, 2, 0]

    result = score_engineering(fenced(source), "E-08")
    assert result["passed"] is True, result
    assert result["positive_points"] == 20, result
    assert result["negative_points"] == 0, result
    assert result["net_points"] == 20, result
    assert "submit_count" in result["obligations_covered"]

    counted_after_submit = source.replace(
        'p("closed", available=0)',
        'p("closed", available=len(x["ids"]))',
    )
    deducted = score_engineering(fenced(counted_after_submit), "E-08")
    assert "submit_count" not in deducted["obligations_covered"]
    assert "deduct_submit_count" in deducted["prohibitions_triggered"]
    assert "evidence_count" in deducted["obligations_covered"]
