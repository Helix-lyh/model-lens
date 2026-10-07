from eval_bank_20260925.bank_manifest import ACTIVE_VERSION, CODE_LANGS, active_item_ids, bank_for_item
from eval_bank_20260925.evaluation import timeout_verdict
from eval_bank_20260925.report import render_markdown
from cursor_workspace.build_scripts import run_eval_20260925 as run_eval
import pytest


def test_active_banks_share_one_version_and_three_languages():
    coding = bank_for_item("CP-09")
    reasoning = bank_for_item("NX-09")
    assert coding.version == reasoning.version == bank_for_item("E-07").version == ACTIVE_VERSION
    assert coding.id == "business-coding"
    assert coding.languages == CODE_LANGS
    assert reasoning.id == "business-reasoning"
    assert active_item_ids(["CP-01", "CP-09"], "hard") == ["CP-09"]


def test_coding_prompt_switches_entry_without_changing_python():
    from eval_bank_20260925.bank_registry import ITEMS
    item = ITEMS.get("CP-09")
    python_prompt = item.prompt("python")
    assert "def describe()" in python_prompt
    assert "python-dateutil" not in python_prompt
    assert "{op,id" not in python_prompt
    go_prompt = ITEMS.get("CP-13").prompt("go")
    assert "func Describe" in go_prompt
    ts_prompt = ITEMS.get("CP-16").prompt("typescript")
    assert "export function describe" in ts_prompt


def test_active_coding_jobs_use_one_language_each():
    from eval_bank_20260925.bank_manifest import ITEM_CODE_LANG, PROGRAMMING_ACTIVE

    items = run_eval.pick_items("hard", bank_profile="active")
    jobs = run_eval.jobs_for(items, ["python", "go", "typescript"])
    coding = [(item.id, lang) for item, lang in jobs if lang is not None]
    assert coding == [(item_id, ITEM_CODE_LANG[item_id]) for item_id in PROGRAMMING_ACTIVE]
    assert [lang for _, lang in coding].count("python") == 4
    assert [lang for _, lang in coding].count("go") == 3
    assert [lang for _, lang in coding].count("typescript") == 3
    assert len(jobs) == 30
    focused = run_eval.jobs_for(run_eval.pick_items("hard", ["CP-09", "E-07", "NX-09"]), ["python", "go", "typescript"])
    assert [(item.id, lang) for item, lang in focused] == [
        ("CP-09", "python"),
        ("E-07", None),
        ("NX-09", None),
    ]


def test_runner_active_registry_objects_replace_legacy_definitions():
    from eval_bank_20260925.bank_manifest import ACTIVE_ITEMS
    from eval_bank_20260925.bank_registry import ITEMS

    for item_id in ACTIVE_ITEMS:
        plugin = ITEMS.get(item_id)
        item = run_eval.ALL_BY_ID[item_id]
        assert item.title == plugin.title
        assert item.prompt == plugin.prompt()
        assert item.kind == plugin.domain
        assert run_eval._item_domain(item_id) == plugin.domain
        if plugin.domain == "coding":
            for language in CODE_LANGS:
                assert run_eval._item_prompt(item, language) == plugin.prompt(language)
        else:
            assert run_eval._item_prompt(item, None) == plugin.prompt()


@pytest.mark.parametrize("item_id", [f"CP-{number:02d}" for number in range(9, 19)])
def test_runner_coding_scorer_dispatches_to_active_plugin(monkeypatch, item_id):
    from eval_bank_20260925.bank_registry import ITEMS

    plugin = ITEMS.get(item_id)
    observed = []

    def score_fn(text, language):
        observed.append((text, language))
        return {"status": "fail", "reason_code": "active_plugin_sentinel", "passed": False,
                "points": 7, "score10": 3.5, "points_total": 20}

    monkeypatch.setattr(type(plugin), "score", lambda self, text, language=None: score_fn(text, language) if self.item_id == item_id else self.score_fn(text, language))
    result = run_eval._score_item(run_eval.ALL_BY_ID[item_id], item_id, "go", "answer")
    assert observed == [("answer", "go")]
    assert result["reason_code"] == "active_plugin_sentinel"
    assert result["points"] == 7


def test_stage_and_final_scores_use_percent():
    verdict = timeout_verdict(type("Q", (), {"id": "NX-09"})(), '{"waiting":[],"last_end":18}')
    assert verdict["score_percent"] == 30.0
    assert verdict["points"] == 6
    text = render_markdown({"experiment_id": "t", "phase": "hard", "langs": ["python"], "samples": 1}, [{
        "bank_id": "business-reasoning",
        "bank_version": ACTIVE_VERSION,
        "channel": "deepseek-flash",
        "item": "NX-09",
        "lang": None,
        "sample": 0,
        "status": "fail",
        "passed": False,
        "points": 6,
        "points_total": 20,
        "score_percent": 30.0,
        "reason_code": "timeout_partial",
        "groups": [{"name": "residue_min", "points": 6, "max": 6, "percent": 100.0}],
    }])
    assert "30.0（6/20）" in text
    assert "residue_min 100.0（6/6）" in text
    assert "没有跨栏总分" in text
