from copy import deepcopy
from dataclasses import replace
import json

import pytest

from eval_bank_20260925.catalog import ITEMS, model_prompt
from eval_bank_20260925.cases import coding_cases
from eval_bank_20260925.oracles import REASONING_ORACLES
from eval_bank_20260925.runner import reference_source, score_coding
from eval_bank_20260925.score import (
    golden,
    parse_json,
    score_reasoning,
    summarize_repair,
)


@pytest.mark.parametrize("item_id", REASONING_ORACLES)
def test_reasoning_goldens_and_missing_fields(item_id):
    expected = golden(item_id)
    result = score_reasoning(item_id, json.dumps(expected))
    assert result.passed and result.points == 20 and result.score10 == 10
    assert score_reasoning(item_id, "{}").points == 0
    for key in expected:
        partial = deepcopy(expected)
        del partial[key]
        result = score_reasoning(item_id, json.dumps(partial))
        assert not result.passed and 0 < result.points < 20


def test_parser_nested_duplicate_bool_and_fraction_contracts():
    data = golden("R-H-01")
    assert parse_json(json.dumps(data)) == data
    assert parse_json("```json\n" + json.dumps(data) + "\n```") == data
    for text in (
        '{"x":1,"x":2}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":1e999}',
        'prefix {"x":1}',
        '{"a":1} {"a":2}',
    ):
        with pytest.raises(ValueError):
            parse_json(text)
    data = deepcopy(golden("R-E-02"))
    data["posterior_u"] = [2, 4]
    assert score_reasoning("R-E-02", json.dumps(data)).passed
    data["posterior_u"] = [True, 2]
    assert not score_reasoning("R-E-02", json.dumps(data)).passed


def test_semantic_witness_and_dependent_points():
    data = deepcopy(golden("R-N-01"))
    data["counterexample"] = {"left": [0, 5, 0], "right": [0, 0, 5]}
    assert score_reasoning("R-N-01", json.dumps(data)).passed
    data["counterexample"] = {"left": [0, 5, 0], "right": [0, 1, 4]}
    assert score_reasoning("R-N-01", json.dumps(data)).points == 16
    data = deepcopy(golden("R-E-01"))
    data["impossible"] = list(range(1, 51))
    result = score_reasoning("R-E-01", json.dumps(data))
    assert result.points == 6
    data = deepcopy(golden("R-H-02"))
    data["base"]["indices"] = []
    result = score_reasoning("R-H-02", json.dumps(data))
    assert next(g for g in result.groups if g["name"] == "delta")["points"] == 0


def test_repair_does_not_splice_rounds_or_erase_partial_credit():
    full = score_reasoning("R-E-02", json.dumps(golden("R-E-02")))
    partial = score_reasoning(
        "R-E-02", json.dumps({"likelihood_u": [1, 1], "likelihood_v": [1, 2]})
    )
    assert partial.points == 8
    single = summarize_repair([partial])
    assert single["discounted_score10"] == 4 and not single["solve_within_k"]
    summary = summarize_repair([partial, full])
    assert summary["discounted_score10"] == 7 and summary["rounds_to_solve"] == 2
    summary = summarize_repair([partial, partial, full])
    assert summary["discounted_score10"] == 4.5 and summary["repair_credit10"] == 4.5
    high = replace(partial, points=18, score10=9)
    assert summarize_repair([high, full])["discounted_score10"] == 9
    missing = replace(
        partial,
        status="missing",
        reason_code="missing_toolchain",
        points=None,
        score10=None,
        passed=None,
    )
    assert summarize_repair([missing])["discounted_score10"] is None
    for rounds in (
        [],
        [partial] * 4,
        [full, partial],
        [partial, replace(partial, item_id="R-E-01")],
        [replace(partial, points=float("nan"))],
    ):
        with pytest.raises(ValueError):
            summarize_repair(rounds)


def test_catalog_prompts_and_check_budgets():
    assert len(ITEMS) == 16 and len({x.id for x in ITEMS}) == 16
    for level in ("easy", "medium", "hard", "extreme"):
        selected = [x for x in ITEMS if x.level == level]
        assert len(selected) == 4 and sum(bool(x.reference) for x in selected) == 2
    for item in ITEMS:
        assert sum(p for _, p in item.groups) == 20
        if item.reference:
            groups = coding_cases(item.id)
            assert len(groups) == 5 and all(len(g) == 4 for g in groups)
            assert all(batch for group in groups for batch in group)
            for lang in ("python", "go", "typescript"):
                assert "POINTS" not in model_prompt(item, lang)
        else:
            assert "参考答案" not in model_prompt(item)


@pytest.mark.parametrize("item", [x for x in ITEMS if x.reference], ids=lambda x: x.id)
def test_python_reference_and_critical_mutant(item):
    source = reference_source(item.id)
    result = score_coding(item.id, "```python\n" + source + "\n```", "python")
    assert result.passed and result.points == 20, result
    mutants = {
        "P-E-01": ("left <= result[-1][1]", "left < result[-1][1]"),
        "P-E-02": (
            'return fields + ["".join(current)]',
            'return fields + (["".join(current)] if not text.endswith(chr(92)) else [])',
        ),
        "P-N-01": ("seen.add(eid)", "pass"),
        "P-N-02": ("if start in seen:", "if start in seen or indegree[start] > 0:"),
        "P-H-01": ("(-x[0], len(x[1]), x[1])", "(-x[0], x[1])"),
        "P-H-02": (
            "last_write.get(k, 0) > snap_version",
            "last_write.get(k, 0) >= snap_version",
        ),
        "P-X-01": ("count[edge] -= 1", "count[edge] = 0"),
        "P-X-02": ('if steps == data["limit"]:', 'if steps > data["limit"]:'),
    }
    before, after = mutants[item.id]
    assert before in source
    result = score_coding(
        item.id, "```python\n" + source.replace(before, after) + "\n```", "python"
    )
    assert (
        not result.passed and 0 < result.points < 20 and len(result.groups) == 5
    ), result


@pytest.mark.parametrize(
    "language,source",
    [
        (
            "go",
            """package solution
import ("encoding/json";"sort")
func Solve(input json.RawMessage) json.RawMessage {
 var d struct {Intervals [][]int `json:"intervals"`}; json.Unmarshal(input,&d)
 sort.Slice(d.Intervals,func(i,j int)bool{return d.Intervals[i][0]<d.Intervals[j][0]})
 result:=make([][]int,0); total:=0
 for _,p:=range d.Intervals {if p[0]==p[1]{continue};if len(result)>0 && p[0]<=result[len(result)-1][1]{if p[1]>result[len(result)-1][1]{result[len(result)-1][1]=p[1]}}else{result=append(result,[]int{p[0],p[1]})}}
 for _,p:=range result{total+=p[1]-p[0]}; out,_:=json.Marshal(map[string]any{"intervals":result,"length":total});return out
}""",
        ),
        (
            "typescript",
            """export function solve(data:any):any {
 const result:number[][]=[]; for(const [a,b] of data.intervals.sort((x:number[],y:number[])=>x[0]-y[0])){
 if(a===b)continue; if(result.length&&a<=result[result.length-1][1])result[result.length-1][1]=Math.max(b,result[result.length-1][1]);else result.push([a,b]);}
 return {intervals:result,length:result.reduce((n,p)=>n+p[1]-p[0],0)};
}""",
        ),
    ],
)
def test_real_go_and_typescript_reference_smoke(language, source):
    result = score_coding("P-E-01", f"```{language}\n{source}\n```", language)
    assert result.passed and result.points == 20, result


def test_missing_and_multiple_fences_do_not_become_model_zero():
    for text in (
        "",
        "def solve(data): return None",
        "```python\ndef solve(d):return 0\n```\n```python\ndef solve(d):return 1\n```",
    ):
        result = score_coding("P-E-01", text, "python")
        assert (
            result.status == "missing"
            and result.points is None
            and result.passed is None
        )


@pytest.mark.parametrize("item", [x for x in ITEMS if x.reference], ids=lambda x: x.id)
@pytest.mark.parametrize("language", ["go", "typescript"])
def test_all_language_references(item, language):
    source = reference_source(item.id, language)
    result = score_coding(item.id, f"```{language}\n{source}\n```", language)
    assert result.passed and result.points == 20, result
