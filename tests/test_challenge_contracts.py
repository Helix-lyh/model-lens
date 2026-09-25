"""CP contract and frozen-oracle regression tests."""

from copy import deepcopy

import pytest

from eval_bank_20260925 import challenge_refs as refs
from eval_bank_20260925.challenge_coding import (
    SPECS,
    cases,
    coding_items,
    reference_source,
    score_saved,
)
from eval_bank_20260925.challenge_goldens_v09 import golden_cases
from eval_bank_20260925.challenge_coding_oracles import ORACLES


def test_cp_contracts_name_entrypoint_encoding_and_public_examples():
    items = {item.id: item for item in coding_items()}
    assert set(items) == {spec[0] for spec in SPECS}
    for item_id, item in items.items():
        assert "def solve(data)" in item.prompt
        assert "公开例" in item.prompt
        assert "只输出一个 python 代码围栏" in item.prompt
        assert len(cases(item_id)) == 5
        assert all(len(group) == 4 for group in cases(item_id))

    assert 'events 统一为数组编码：["ADD",rule_id,rule]' in items["CP-03"].prompt
    assert 'events 统一为数组编码：["BATCH",batch_id,rows]' in items["CP-05"].prompt
    assert 'events 统一为数组编码：["INGEST",event_id,entity,timestamp,value]' in items["CP-06"].prompt
    assert "立即终止，保留 PENDING" in items["CP-07"].prompt
    assert "when 缺省视为 false" in items["CP-08"].prompt
    assert "状态保持 SHIPPED" in items["CP-01"].prompt
    assert "每个 depends 都已经是 DONE" in items["CP-02"].prompt
    assert "不含冒号" in items["CP-03"].prompt
    assert "更具体" in items["CP-04"].prompt
    assert "tx_id 立即释放" in items["CP-05"].prompt
    assert "也不追溯" in items["CP-06"].prompt
    assert "都不归还" in items["CP-07"].prompt
    assert "本阶段开始时" in items["CP-08"].prompt


def test_frozen_expected_values_do_not_execute_reference_functions(monkeypatch):
    cases.cache_clear()
    before = deepcopy(cases("CP-01"))
    monkeypatch.setattr(refs, "order_processor", lambda data: {"tampered": True})
    cases.cache_clear()
    after = cases("CP-01")
    assert [[case.expected for batch in group for case in batch] for group in after] == [
        [case.expected for batch in group for case in batch] for group in before
    ]
    assert golden_cases("CP-01")[0][0][1] == before[0][0][0].expected


@pytest.mark.parametrize("item_id", [spec[0] for spec in SPECS])
def test_every_frozen_golden_matches_independent_oracle(item_id):
    for group in golden_cases(item_id):
        for data, expected in group:
            assert ORACLES[item_id](data) == expected


@pytest.mark.parametrize("item_id", [spec[0] for spec in SPECS])
def test_python_reference_replays_all_frozen_cp_goldens(item_id):
    source = reference_source(item_id)
    # score_saved is a legacy marker runner; CP-07's formerly unbounded
    # deadlock case is verified directly below and by the new parent-owned runner.
    result = score_saved(item_id, chr(96) * 3 + "python\n" + source + "\n" + chr(96) * 3)
    assert result["status"] == "pass", (item_id, result)
    assert result["passed"] is True
    assert result["points"] == 20


def test_resource_schedule_advances_to_completion_when_no_pending_jobs():
    from eval_bank_20260925.challenge_refs import resource_schedule

    result = resource_schedule({
        "workers": 1,
        "resources": {},
        "jobs": [{"id": "a", "release": 0, "duration": 1, "priority": 1, "deadline": 2, "needs": [], "deps": []}],
        "cancel": [],
    })
    assert result == {"schedule": [["a", 0, 1, 0, False]], "states": [["a", "DONE"]]}


def test_cp_boundary_semantics_are_terminating_and_atomic():
    assert refs.order_processor(
        {"initial": {"a": 1}, "events": [
            {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 2]]},
            {"op": "RESERVE", "id": "r", "order": "o2", "lines": [["a", 1]]},
        ]}
    )["trace"] == ["REJECT", "DUP"]
    assert refs.event_aggregate(
        {"window": 10, "events": [
            ["RETRACT", "op", "missing"],
            ["INGEST", "e", "a", 1, 3],
            ["RETRACT", "op", "e"],
            ["QUERY", "a", 1],
        ]}
    ) == [{"entity": "a", "start": 0, "count": 1, "sum": 3, "ids": ["e"]}]
    assert refs.resource_schedule(
        {"workers": 1, "resources": {}, "jobs": [
            {"id": "blocked", "release": 0, "duration": 1, "priority": 1,
             "deadline": 1, "needs": [], "deps": ["missing"]},
        ], "cancel": []}
    ) == {"schedule": [], "states": [["blocked", "PENDING"]]}


def test_rule_changed_tracks_actual_state_changes_only():
    data = {
        "facts": {"tags": ["x"], "kept": True},
        "rules": [
            {"id": "duplicate", "phase": "main", "when": {"op": "exists", "field": "tags"},
             "set": {"kept": True}, "add": {"tags": "x"}, "remove": ["absent"]},
            {"id": "watch", "phase": "post", "when": {"op": "changed", "field": "tags"},
             "set": {"bad": True}, "add": {}, "remove": []},
        ],
    }
    expected = {"facts": [["kept", True], ["tags", ["x"]]], "fired": ["duplicate"],
                "conflicts": [], "stopped": False}
    assert refs.rule_engine(data) == expected
    assert ORACLES["CP-08"](data) == expected


def test_v09_counterconventional_rules_are_specified_and_enforced():
    """每个新陷阱都有题面原句，并且参考实现与独立 oracle 给出同一结果。"""
    agreed = {
        "CP-03": (
            {"roles": {"r": []}, "users": {"u": ["r"]}, "events": [
                ["ADD", "d", {"effect": "deny", "role": "r", "action": "read", "resource": "doc:*"}],
                ["ADD", "a", {"effect": "allow", "role": "r", "action": "read", "resource": "*"}],
                ["CHECK", "u", "read", "doc:1", 0],
                ["CHECK", "u", "read", "doc:1:2", 0],
            ]},
            ["DENY", "ALLOW"],
        ),
        "CP-06": (
            {"window": 10, "events": [
                ["INGEST", "e", "a", 1, 3],
                ["SEAL", "s", "a", 1],
                ["INGEST", "late", "a", 2, 9],
                ["QUERY", "a", 1],
            ]},
            [{"entity": "a", "start": 0, "count": 1, "sum": 3, "ids": ["e"]}],
        ),
        "CP-08": (
            {"facts": {"x": 1}, "rules": [
                {"id": "p", "phase": "pre", "priority": 1, "when": {"op": "exists", "field": "x"},
                 "set": {"x": 2}, "add": {}, "remove": []},
                {"id": "m", "phase": "main", "priority": 1, "when": {"op": "changed", "field": "x"},
                 "set": {"bad": True}, "add": {}, "remove": []},
            ]},
            {"facts": [["x", 2]], "fired": ["p"], "conflicts": [], "stopped": False},
        ),
    }
    callers = {"CP-03": refs.permission_engine, "CP-06": refs.event_aggregate, "CP-08": refs.rule_engine}
    for item_id, (data, expected) in agreed.items():
        assert callers[item_id](data) == expected
        assert ORACLES[item_id](data) == expected
