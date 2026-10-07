from eval_bank_20260925.bank_manifest import active_item_ids, adapter_for_item, bank_status
from eval_bank_20260925.bank_adapters import ADAPTERS, FunctionalAdapter, scorer_fingerprint
from eval_bank_20260925.evaluation import aggregate_groups, pass_at_k, scoring_provenance, timeout_verdict


def _nx09():
    return type("Q", (), {"id": "NX-09"})()


def test_timeout_contract_scores_empty_response_as_judged_zero():
    verdict = timeout_verdict(_nx09(), "")
    assert verdict["status"] == "fail"
    assert verdict["reason_code"] == "timeout"
    assert verdict["passed"] is False
    assert verdict["points"] == 0
    assert verdict["score10"] == 0.0


def test_timeout_keeps_fixture_and_runtime_errors_unjudged():
    item = type("Q", (), {"id": "CP-09"})()

    def errored(_item, _text):
        return {"status": "error", "reason_code": "grader_error", "passed": None, "points": None, "score10": None}

    verdict = timeout_verdict(item, "partial", scorer=errored)
    assert verdict["status"] == "error"
    assert verdict["reason_code"] == "grader_error"
    assert verdict["points"] is None


def test_timeout_empty_coding_and_engineering_are_judged_zero():
    coding = timeout_verdict(type("Q", (), {"id": "CP-09"})(), "")
    assert coding["status"] == "fail"
    assert coding["reason_code"] == "timeout"
    assert coding["passed"] is False
    assert coding["points"] == 0
    assert coding["score10"] == 0.0

    engineering = timeout_verdict(type("Q", (), {"id": "E-07"})(), "")
    assert engineering["status"] == "fail"
    assert engineering["reason_code"] == "timeout"
    assert engineering["passed"] is False
    assert engineering["points"] == 0
    assert engineering["net_points"] == 0
    assert engineering["positive_points"] == 0
    assert engineering["negative_points"] == 0
    assert engineering["score10"] is None


def test_cp17_integer_reads_are_not_observations():
    from eval_bank_20260925.coding_facts import cp17

    assert cp17({"reads": 3, "miss": 1}) == []
    assert cp17({"reads": [{"key": "k", "miss": True}]}) == [{"key": "k", "miss": True, "value": None}]


def test_matrix_gate_rejects_split_prompts_and_blank_scorer():
    from cursor_workspace.build_scripts.build_eval_matrix import check_comparable

    meta = {"models": ["a", "b"], "items": ["CP-09"]}
    left = {
        "channel": "a", "item": "CP-09", "scorer_sha256": "ab", "bank_version": "20261008",
        "base_prompt_sha256": "p", "lang": "python",
    }
    right = dict(left, channel="b")
    check_comparable(meta, [left, right])
    try:
        check_comparable(meta, [left, dict(right, base_prompt_sha256="q")])
    except SystemExit as exc:
        assert "题面" in str(exc)
    else:
        raise AssertionError("不同题面被放进了同一页")
    try:
        check_comparable(meta, [left, dict(right, scorer_sha256="")])
    except SystemExit as exc:
        assert "判定脚本" in str(exc)
    else:
        raise AssertionError("空的判定脚本哈希被放进了同一页")
    try:
        check_comparable(meta, [left, dict(right, lang="go")])
    except SystemExit as exc:
        assert "语言" in str(exc)
    else:
        raise AssertionError("不同语言被放进了同一页")


def test_timeout_contract_preserves_parseable_groups_but_never_passes():
    verdict = timeout_verdict(_nx09(), '{"waiting":[],"last_end":18}')
    assert verdict["status"] == "fail"
    assert verdict["reason_code"] == "timeout_partial"
    assert verdict["passed"] is False
    assert verdict["points"] == 6
    assert verdict["score10"] == 3.0


def test_pass_at_k_keeps_timeout_sample_in_the_population():
    rows = [
        {"item": "R-E-01", "lang": None, "status": "fail", "passed": False},
        {"item": "R-E-01", "lang": None, "status": "pass", "passed": True},
        {"item": "R-E-01", "lang": None, "status": "fail", "passed": False},
    ]
    assert pass_at_k(rows, 2)[0] == 0.6667


def test_manifest_limits_active_smoke_to_the_live_columns():
    assert bank_status("business-coding") == "active"
    assert bank_status("business-engineering") == "active"
    assert bank_status("business-reasoning") == "active"
    assert active_item_ids(["CP-09", "E-01", "NX-09", "CP-01"], "hard") == ["CP-09", "E-01", "NX-09"]
    assert active_item_ids(["CP-09", "E-07", "NX-09", "E-01"], "quick") == ["CP-09", "E-07", "NX-09"]


def test_manifest_selects_pluggable_bank_adapters():
    assert adapter_for_item("CP-09") == "coding"
    assert adapter_for_item("E-01") == "engineering"
    assert adapter_for_item("NX-09") == "reasoning"
    assert {adapter_for_item(item_id) for item_id in ("CP-09", "E-01", "NX-09")} <= ADAPTERS.adapter_ids


def test_active_items_are_resolvable_plugins():
    from eval_bank_20260925.bank_manifest import ACTIVE_ITEMS
    from eval_bank_20260925.bank_registry import ITEMS

    assert ACTIVE_ITEMS
    assert all(ITEMS.resolve(item_id).item_id == item_id for item_id in ACTIVE_ITEMS)


def test_every_manifest_adapter_renders_and_has_stable_scoring_identity():
    from eval_bank_20260925.bank_adapters import render_item_prompt

    item = _nx09()
    prompt = render_item_prompt(item)
    identity = scoring_provenance(item)
    assert prompt
    assert identity["adapter_id"] == "reasoning"
    assert len(identity["scorer_sha256"]) == 64
    assert identity["scorer_sha256"] == scorer_fingerprint(item)


def test_adapter_registry_rejects_accidental_replacement_and_allows_explicit_plugin():
    registry_adapter = FunctionalAdapter(lambda item, language: item.prompt, lambda item, text, language: {})
    from eval_bank_20260925.bank_adapters import AdapterRegistry

    registry = AdapterRegistry()
    registry.register("custom", registry_adapter)
    assert registry.resolve("custom") is registry_adapter
    try:
        registry.register("custom", registry_adapter)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate adapter registration should fail")
    registry.register("custom", registry_adapter, replace=True)


def test_column_summary_accumulates_points_without_cross_column_total():
    from eval_bank_20260925.evaluation import summarize

    rows = [
        {"channel": "stub", "experiment_id": "run", "item": "CP-01", "lang": "python", "sample": 0,
         "status": "pass", "passed": True, "points": 20, "points_total": 20, "score10": 10},
        {"channel": "stub", "experiment_id": "run", "item": "CP-01", "lang": "python", "sample": 1,
         "status": "fail", "passed": False, "points": 10, "points_total": 20, "score10": 5},
    ]
    summary = summarize(rows, pass_k=2)
    assert summary["points"] == 30
    assert summary["points_total"] == 40
    assert summary["score_percent_total"] == 75.0
    assert summary["pass_at_1"] == 0.5
    assert summary["pass_at_k"] == 1.0
    assert summary["questions"] == 1
    assert summary["attempted_samples"] == 2


def test_engineering_summary_reports_signed_total_and_strict_pass_at_k():
    from eval_bank_20260925.evaluation import summarize_engineering

    rows = [
        {"channel": "stub", "experiment_id": "run", "item": "E-01", "lang": None, "sample": 0,
         "status": "pass", "passed": True, "positive_points": 20, "negative_points": 0, "net_points": 20},
        {"channel": "stub", "experiment_id": "run", "item": "E-01", "lang": None, "sample": 1,
         "status": "fail", "passed": False, "positive_points": 14, "negative_points": 2, "net_points": 12},
    ]
    summary = summarize_engineering(rows, pass_k=2)
    assert summary["positive_points"] == 34
    assert summary["negative_points"] == 2
    assert summary["net_points"] == 32
    assert summary["points_total"] == 40
    assert summary["net_percent_total"] == 80.0
    assert summary["pass_at_1"] == 0.5
    assert summary["pass_at_k"] == 1.0
    assert summary["questions"] == 1
    assert summary["attempted_samples"] == 2


def test_group_totals_accumulate_across_items_but_keep_bank_revision_separate():
    rows = [
        {"bank_id": "b", "bank_version": "1", "groups": [{"name": "state", "points": 3, "max": 5}]},
        {"bank_id": "b", "bank_version": "1", "groups": [{"name": "state", "points": 4, "max": 5}]},
        {"bank_id": "b", "bank_version": "2", "groups": [{"name": "state", "points": 1, "max": 5}]},
    ]
    totals = aggregate_groups(rows)
    assert totals == [
        {"bank_id": "b", "bank_version": "1", "name": "state", "points": 7, "max": 10, "percent": 70.0},
        {"bank_id": "b", "bank_version": "2", "name": "state", "points": 1, "max": 5, "percent": 20.0},
    ]


def test_pass_at_k_rejects_duplicate_sample_identity():
    row = {"experiment_id": "run", "channel": "model", "bank_id": "b", "bank_version": "1",
           "item": "q1", "lang": None, "sample": 0, "status": "pass", "passed": True}
    try:
        pass_at_k([row, dict(row)], 1)
    except ValueError as exc:
        assert "duplicate logical sample" in str(exc)
    else:
        raise AssertionError("duplicate samples must not inflate pass@k")
