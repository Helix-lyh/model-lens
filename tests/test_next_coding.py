"""Executable-contract checks for the 20261008 coding bank."""

import json

import pytest

from eval_bank_20260925.coding_facts import cp14 as facts_cp14, cp16 as facts_cp16, cp17 as facts_cp17
from eval_bank_20260925.next_coding import contract_equal, cp09, cp12, cp13, cp18, prompt, reference_source, score_saved

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


def test_prompt_states_the_shared_envelope() -> None:
    text = prompt("CP-10", "python")
    assert "只能有 trace 和 output 两个键" in text
    assert "def describe()" in text
    assert "def solve(data)" in text
    assert "只输出一个 python 代码围栏" in text
    assert "output.parcels" not in text
    assert "DUP" in text


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


def test_cp16_token_counts_match_without_echoed_tenant():
    echoed = {"reads": [{"tenant": "t", "tenant_tokens": 1, "global_tokens": 3}]}
    omitted = {"reads": [{"tenant_tokens": 1, "global_tokens": 3}]}
    assert facts_cp16(echoed) == facts_cp16(omitted)
    assert facts_cp16({"reads": [{"tenant": "t", "tenant_tokens": 0, "global_tokens": 3}]}) != facts_cp16(omitted)


def test_cp17_string_and_top_level_miss_count_as_miss():
    object_miss = {"reads": [{"key": "k", "miss": True, "value": None}]}
    string_miss = {"reads": ["k"]}
    listed_miss = {"reads": [], "miss": ["k"]}
    assert facts_cp17(object_miss) == facts_cp17(string_miss) == facts_cp17(listed_miss)
    assert facts_cp17(string_miss) == [{"key": "k", "miss": True, "value": None}]
    hit = {"reads": [{"key": "k", "value": "a"}], "miss": ["x"]}
    assert facts_cp17(hit) == [
        {"key": "k", "miss": False, "value": "a"},
        {"key": "x", "miss": True, "value": None},
    ]
