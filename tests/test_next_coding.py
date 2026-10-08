"""Executable-contract checks for the 20261008 coding bank."""

import json

import pytest

from eval_bank_20260925.coding_facts import cp09 as facts_cp09, cp12 as facts_cp12, cp14 as facts_cp14, cp16 as facts_cp16, cp17 as facts_cp17, cp18 as facts_cp18
from eval_bank_20260925.next_coding import contract_equal, cp09, cp12, cp13, cp14, cp18, prompt, reference_source, score_saved

_OLD_CODE_LANG = {
    "CP-09": "python", "CP-10": "python", "CP-11": "python", "CP-12": "python",
    "CP-13": "go", "CP-14": "go", "CP-15": "go",
    "CP-16": "typescript", "CP-17": "typescript", "CP-18": "typescript",
}
from eval_bank_20260925.describe_contract import coding_envelope_equal, is_coding_envelope


@pytest.mark.parametrize(("item_id", "language"), tuple(_OLD_CODE_LANG.items()))
def test_reference_answer_passes_assigned_language(item_id: str, language: str) -> None:
    source = reference_source(item_id, language)
    fenced = f"```{language}\n{source}\n```"
    result = score_saved(item_id, fenced, language)
    assert result["status"] == "pass", (item_id, language, result)
    assert result["points"] == 20
    assert result["passed"] is True


def test_reference_source_rejects_unknown_language() -> None:
    with pytest.raises(ValueError, match="unsupported language"):
        reference_source("CP-09", "rust")


def test_fixture_does_not_rename_the_input():
    from eval_bank_20260925.next_coding import _SCHEMAS, _fixture, cases
    schema, groups = _SCHEMAS["CP-12"], cases("CP-12")
    python = _fixture(schema, groups, "MARK", "python")
    go = _fixture(schema, groups, "MARK", "go")
    typescript = _fixture(schema, groups, "MARK", "typescript")
    assert "solve(adapt_input" not in python
    assert "solve(copy.deepcopy(data))" in python
    assert "return Solve(encoded)" not in go
    assert "return Solve(input)" in go
    assert "solve(input)" in typescript
    assert "renameTree(JSON.parse" not in typescript


def test_prompt_states_the_shared_envelope() -> None:
    text = prompt("CP-10", "python")
    assert "只能有 trace 和 output 两个键" in text
    assert "def describe()" in text
    assert "def solve(data)" in text
    assert "只输出一个 python 代码围栏" in text
    assert "output.parcels" not in text
    assert "DUP" in text
    assert "无法判分" not in text
    assert "夹具" not in text


def test_cp09_oracle_uses_only_the_new_envelope() -> None:
    got = cp09({"quota": {"a": 2}, "events": [
        {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]},
        {"op": "SNAP", "id": "s"},
        {"op": "RELEASE", "id": "x", "order": "o"},
        {"op": "RESTORE", "id": "z", "snapshot": 0},
    ]})
    assert set(got) == {"trace", "output"}
    assert got["trace"] == ["OK", "SNAP", "OK", "RESTORE"]
    assert got["output"]["quota"] == {"a": 1}
    assert got["output"]["orders"] == {"o": "RESERVED"}
    assert got["output"]["snapshots"]["0"]["orders"] == {"o": "RESERVED"}
    historical = {"trace": got["trace"], "quota": [["a", 1]], "orders": [["o", "RESERVED"]], "snapshots": [0]}
    assert is_coding_envelope(historical) is False
    assert coding_envelope_equal(historical, got) is False
    assert coding_envelope_equal(got, got) is True


def test_cp13_read_object_has_no_legacy_account_field() -> None:
    got = cp13({"accounts": {"a": 10}, "events": [
        {"op": "HOLD", "id": "1", "account": "a", "hold": "h", "amount": 6},
        {"op": "READ", "id": "2", "account": "a"},
    ]})
    assert set(got) == {"trace", "output"}
    read = got["output"]["reads"][0]
    assert set(read) == {"balance", "available", "holds"}
    assert read["holds"] == [{"hold": "h", "state": "HELD", "remaining": 6}]


def test_wrong_output_inside_the_envelope_does_not_match() -> None:
    expected = cp09({"quota": {"a": 1}, "events": [{"op": "READ", "id": "q", "order": "missing"}]})
    got = {"trace": list(expected["trace"]), "output": {**expected["output"], "quota": {"a": 0}}}
    assert is_coding_envelope(got) is True
    assert contract_equal("CP-09", got, expected) is False


def test_unspecified_trace_word_passes_when_output_matches() -> None:
    expected = cp09({"quota": {"a": 1}, "events": [{"op": "RESTORE", "id": "r", "snapshot": 9}]})
    got = {"trace": ["REJECT"], "output": expected["output"]}
    assert expected["trace"] == ["INVALID"]
    assert contract_equal("CP-09", got, expected) is True


def test_prompt_named_dup_is_still_strict() -> None:
    expected = cp09({"quota": {"a": 1}, "events": [
        {"op": "READ", "id": "q", "order": "missing"},
        {"op": "READ", "id": "q", "order": "missing"},
    ]})
    assert expected["trace"][1] == "DUP"
    got = {"trace": ["MISSING", "OK"], "output": expected["output"]}
    assert contract_equal("CP-09", got, expected) is False


def test_cp18_change_reads_new_price_and_old_price_is_not_full_score():
    got = cp18({"fares": [
        {"id": "a", "from": "x", "to": "y", "start": 0, "end": 100, "price": 101},
        {"id": "b", "from": "x", "to": "y", "start": 50, "end": 100, "price": 203},
    ], "events": [
        {"op": "BUY", "id": "1", "ticket": "t", "from": "x", "to": "y", "depart": 10, "at": 1},
        {"op": "CHANGE", "id": "2", "ticket": "t", "new_depart": 60},
        {"op": "READ", "id": "3", "ticket": "t"},
    ]})
    assert got["output"]["reads"] == [
        {"ticket": "t", "state": "CHANGED", "price": 101, "refund": 0},
        {"ticket": "t", "state": "ACTIVE", "price": 203, "refund": 0},
    ]
    overwritten = {"reads": [{"ticket": "t", "state": "ACTIVE", "price": 203, "refund": 0}]}
    assert facts_cp18(overwritten) != facts_cp18(got["output"])
    blocked = cp18({"fares": [
        {"id": "a", "from": "x", "to": "y", "start": 0, "end": 100, "price": 100},
        {"id": "b", "from": "x", "to": "y", "start": 90, "end": 100, "price": 250},
    ], "events": [
        {"op": "BUY", "id": "1", "ticket": "t", "from": "x", "to": "y", "depart": 80, "at": 1},
        {"op": "REFUND", "id": "2", "ticket": "t", "at": 1},
        {"op": "CHANGE", "id": "3", "ticket": "t", "new_depart": 95},
        {"op": "READ", "id": "4", "ticket": "t"},
    ]})
    assert blocked["output"]["reads"] == [{"ticket": "t", "state": "REFUNDED", "price": 100, "refund": 90}]
    source = reference_source("CP-18")
    old = 'tickets[e["ticket"]+"#current"]={**t,"state":"ACTIVE","depart":e["new_depart"],"price":f["price"]}'
    new = 'tickets[e["ticket"]+"#current"]={**t,"state":"ACTIVE","depart":e["new_depart"],"price":t["price"]}'
    assert old in source
    broken = source.replace(old, new, 1)
    result = score_saved("CP-18", f"```python\n{broken}\n```", "python")
    assert result["passed"] is False
    assert result["points"] != 20


def test_unnamed_ticket_state_is_not_a_character_check() -> None:
    expected = cp18({"fares": [{"id": "a", "from": "A", "to": "B", "start": 0, "end": 100, "price": 100}], "events": [
        {"op": "BUY", "id": "1", "ticket": "t", "from": "A", "to": "B", "depart": 10, "at": 0},
        {"op": "READ", "id": "2", "ticket": "t"},
    ]})
    got = json.loads(json.dumps(expected))
    got["output"]["reads"][0]["state"] = "VALID"
    assert expected["output"]["reads"][0]["state"] == "ACTIVE"
    assert contract_equal("CP-18", got, expected) is True
    got["output"]["reads"][0]["price"] = 1
    assert contract_equal("CP-18", got, expected) is False


def test_cp09_missing_snapshots_do_not_match_reference():
    got = cp09({"quota": {"a": 2}, "events": [
        {"op": "RESERVE", "id": "r", "order": "o", "lines": [["a", 1]]},
        {"op": "SNAP", "id": "s"},
        {"op": "RELEASE", "id": "x", "order": "o"},
        {"op": "RESTORE", "id": "z", "snapshot": 0},
    ]})
    omitted = {key: value for key, value in got["output"].items() if key != "snapshots"}
    assert facts_cp09(got["output"])["snapshots"] == [
        {"id": "0", "quota": {"a": 1}, "orders": {"o": "RESERVED"}},
    ]
    assert facts_cp09(omitted) != facts_cp09(got["output"])


def test_cp12_wrong_snapshot_edges_do_not_match_reference():
    got = cp12({"tenants": ["t"], "events": [
        {"op": "CREATE", "id": "1", "tenant": "t", "user": "a"},
        {"op": "CREATE", "id": "2", "tenant": "t", "user": "b"},
        {"op": "MERGE", "id": "3", "tenant": "t", "from": "a", "to": "b"},
        {"op": "SNAP", "id": "4"},
        {"op": "SPLIT", "id": "5", "tenant": "t", "from": "a", "to": "b"},
    ]})
    assert got["output"]["edges"] == []
    assert got["output"]["snapshots"] == [[{"tenant": "t", "from": "a", "to": "b"}]]
    omitted = {key: value for key, value in got["output"].items() if key != "snapshots"}
    wrong = json.loads(json.dumps(got["output"]))
    wrong["snapshots"] = [[{"tenant": "t", "from": "b", "to": "a"}]]
    assert facts_cp12(got["output"])["roots"] == facts_cp12(omitted)["roots"]
    assert facts_cp12(got["output"])["edges"] == facts_cp12(omitted)["edges"]
    assert facts_cp12(omitted) != facts_cp12(got["output"])
    assert facts_cp12(wrong) != facts_cp12(got["output"])


def test_cp12_split_removes_only_the_current_direct_edge():
    got = cp12({"tenants": ["t"], "events": [
        {"op": "CREATE", "id": "1", "tenant": "t", "user": "a"},
        {"op": "CREATE", "id": "2", "tenant": "t", "user": "b"},
        {"op": "CREATE", "id": "3", "tenant": "t", "user": "c"},
        {"op": "MERGE", "id": "4", "tenant": "t", "from": "a", "to": "b"},
        {"op": "MERGE", "id": "5", "tenant": "t", "from": "b", "to": "c"},
        {"op": "SPLIT", "id": "6", "tenant": "t", "from": "a", "to": "b"},
    ]})
    assert got["output"]["edges"] == [{"tenant": "t", "from": "b", "to": "c"}]


def test_cp14_ignores_undefined_expired_boolean():
    same = {"reads": [{"sku": "s", "free": 0, "locked": 1}], "orders": {"o": "ALLOCATED"}}
    with_true = {"reads": [{"sku": "s", "batches": [{"free": 0, "locked": 1, "expired": True}]}], "orders": [{"order": "o", "state": "ALLOCATED"}]}
    with_zero = {"reads": [{"sku": "s", "batches": [{"free": 0, "locked": 1, "expired": 0}]}], "orders": [{"order": "o", "state": "ALLOCATED"}]}
    assert facts_cp14(with_true) == facts_cp14(with_zero)
    assert facts_cp14(with_true)["reads"][0]["free"] == same["reads"][0]["free"]
    changed = {"reads": [{"sku": "s", "batches": [{"free": 1, "locked": 1, "expired": True}]}], "orders": [{"order": "o", "state": "ALLOCATED"}]}
    assert facts_cp14(with_true) != facts_cp14(changed)


def test_cp14_totals_match_without_a_batch_list():
    got = cp14({"batches": [
        {"sku": "s", "batch": "b1", "qty": 2, "expiry": 5, "received": 1},
        {"sku": "s", "batch": "b2", "qty": 2, "expiry": 8, "received": 2},
    ], "events": [
        {"op": "ALLOCATE", "id": "1", "order": "o", "sku": "s", "qty": 3, "at": 1},
        {"op": "READ", "id": "2", "sku": "s", "at": 1},
    ]})
    reference = facts_cp14(got["output"])["reads"][0]
    totals = {"reads": [{"sku": "s", "free": reference["free"], "locked": reference["locked"]}], "orders": got["output"]["orders"]}
    assert facts_cp14(totals) == facts_cp14(got["output"])
    wrong = {"reads": [{"sku": "s", "free": 9, "locked": 0}], "orders": got["output"]["orders"]}
    assert facts_cp14(wrong) != facts_cp14(got["output"])
    assert reference["free"] == 1 and reference["locked"] == 3
    assert facts_cp14({"reads": [{"sku": "s", "batches": [{}]}]}) != facts_cp14(got["output"])
    assert facts_cp14({"reads": [{"sku": "s", "batches": [{"expired": True}]}]}) != facts_cp14(got["output"])


def test_cp16_token_counts_match_without_echoed_tenant():
    echoed = {"reads": [{"tenant": "t", "tenant_tokens": 1, "global_tokens": 3}]}
    omitted = {"reads": [{"tenant_tokens": 1, "global_tokens": 3}]}
    assert facts_cp16(echoed) == facts_cp16(omitted)
    assert facts_cp16({"reads": [{"tenant": "t", "tenant_tokens": 0, "global_tokens": 3}]}) != facts_cp16(omitted)


def test_cp17_only_a_read_without_a_value_is_a_miss():
    object_miss = {"reads": [{"key": "k", "miss": True, "value": None}]}
    assert facts_cp17(object_miss) == [{"key": "k", "miss": True, "value": None}]
    assert facts_cp17({"reads": ["k"]}) == []
    assert facts_cp17({"reads": [], "miss": ["k"]}) == []
    assert facts_cp17({"reads": {}, "miss": {"2": "k"}}) == [{"key": "k", "miss": True, "value": None}]
    leaked = {"reads": [{"key": "k", "miss": True, "value": "a"}]}
    assert facts_cp17(leaked) != facts_cp17(object_miss)
    hit = {"reads": [{"key": "k", "value": "a", "version": 1}], "miss": ["x"]}
    assert facts_cp17(hit) == [{"key": "k", "miss": False, "value": "a"}]
    assert facts_cp17({"reads": {"k": "a"}, "miss": {"2": "k"}}) == [{"key": "k", "miss": True, "value": "a"}]
    assert facts_cp17({"reads": {"2": "a"}, "miss": {"2": "k"}}) == [{"key": "k", "miss": True, "value": "a"}]
