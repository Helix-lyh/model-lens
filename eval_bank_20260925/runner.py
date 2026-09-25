"""复用仓库语言运行器；生成三语言同源 fixtures；不发起模型请求。"""

import inspect
import json
from pathlib import Path
import re
import secrets
import tempfile

from src.grade import grade_response
from src.types import Question

from . import references
from .cases import coding_cases
from .catalog import BY_ID
from .score import Score


def reference_source(item_id, language="python"):
    item = BY_ID[item_id]
    if language in {"go", "typescript"}:
        names = {
            "merge_intervals": "mergeIntervals",
            "escaped_split": "escapedSplit",
            "atomic_stock": "atomicStock",
            "dependency_order": "dependencyOrder",
            "weighted_schedule": "weightedSchedule",
            "snapshot_transactions": "snapshotTransactions",
            "dynamic_connectivity": "dynamicConnectivity",
            "register_machine": "registerMachine",
        }
        extension = "go" if language == "go" else "ts"
        code = (
            Path(__file__)
            .with_name(f"references.{extension}")
            .read_text(encoding="utf-8")
        )
        name = names[item.reference]
        return code + (
            f"\nfunc Solve(input json.RawMessage) json.RawMessage {{ return {name}(input) }}\n"
            if language == "go"
            else f"\nexport function solve(data:any):any {{ return {name}(data); }}\n"
        )
    if language != "python":
        raise ValueError("unknown_language")
    fn = getattr(references, item.reference)
    source = inspect.getsource(fn)
    return source.replace(f"def {item.reference}(", "def solve(", 1)


def _payload(groups):
    return [
        [
            [{"input": case.data, "expected": case.expected} for case in batch]
            for batch in group
        ]
        for group in groups
    ]


def _input_payload(groups):
    return [[[case.data for case in batch] for batch in group] for group in groups]


def python_result_fixture(groups, marker):
    blob = json.dumps(_input_payload(groups), ensure_ascii=True, separators=(",", ":"))
    return f"""import contextlib
import copy
import io
import json
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from solution import solve
groups = json.loads({blob!r})
case_no = 0
for group in groups:
    for batch in group:
        for data in batch:
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    got = solve(copy.deepcopy(data))
                encoded = json.dumps(got, ensure_ascii=True, separators=(",", ":"))
            except BaseException:
                encoded = "null"
            print({marker!r} + " CASE " + str(case_no) + " " + encoded)
            case_no += 1
"""


def go_result_fixture(groups, marker):
    blob = json.dumps(_input_payload(groups), ensure_ascii=True, separators=(",", ":"))
    return (
        """package solution
import ("encoding/json"; "fmt"; "testing")
func TestContent20260925(t *testing.T) {
  var groups [][][]json.RawMessage
  if err := json.Unmarshal([]byte("""
        + json.dumps(blob)
        + """), &groups); err != nil { t.Fatal(err) }
  caseNo:=0
  for _, group := range groups { for _, batch := range group { for _, input := range batch {
    got := func() (out json.RawMessage) { defer func(){ if recover()!=nil { out=[]byte("null") } }(); return Solve(input) }()
    if len(got)==0 { got=[]byte("null") }
    fmt.Printf("%s CASE %d %s\\n", """ + json.dumps(marker) + """, caseNo, got)
    caseNo++
  } } }
}
"""
    )


def ts_result_fixture(groups, marker):
    blob = json.dumps(_input_payload(groups), ensure_ascii=True, separators=(",", ":"))
    return (
        """declare const require: any;
const {solve} = require("./solution");
const groups: any = """
        + blob
        + ";\n"
        + """let caseNo=0;
for (const group of groups) for (const batch of group) for (const input of batch) {
  let got:any = null;
  try { const old=console.log; console.log=()=>{}; got=solve(JSON.parse(JSON.stringify(input))); console.log=old; } catch { console.log=()=>{}; }
  let encoded="null"; try { encoded=JSON.stringify(got); } catch {}
  console.log(""" + json.dumps(marker) + """ + ` CASE ${caseNo} ${encoded}`);
  caseNo++;
}
"""
    )


def _score_case_results(item_id, groups, detail, language, group_defs=None):
    marker_lines = [line for line in detail.splitlines() if line.startswith("CASE ")]
    if not marker_lines:
        return None
    got_by_index = {}
    for line in marker_lines:
        match = re.fullmatch(r"CASE (\d+) (.*)", line)
        if not match:
            continue
        try:
            got_by_index[int(match.group(1))] = json.loads(match.group(2))
        except (ValueError, TypeError, json.JSONDecodeError):
            got_by_index[int(match.group(1))] = object()
    offset = 0
    earned = 0
    breakdown = []
    definitions = group_defs or BY_ID[item_id].groups
    if len(definitions) != len(groups):
        return None
    for group_index, (name, _budget) in enumerate(definitions):
        group_points = 0
        for group in [groups[group_index]]:
            for batch in group:
                ok = True
                for case in batch:
                    index = offset
                    got = got_by_index.get(index, object())
                    ok = ok and _strict_equal(got, case.expected)
                    offset += 1
                group_points += int(ok)
        earned += group_points
        breakdown.append({"name": name, "points": group_points, "max": 4})
    passed = earned == 20
    return Score(item_id, language, "pass" if passed else "fail", "ok" if passed else "tests_failed", float(earned), 20, earned / 2, passed, breakdown, True)


def _strict_equal(got, expected):
    if type(got) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(got) == set(expected) and all(_strict_equal(got[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(got) == len(expected) and all(_strict_equal(a, b) for a, b in zip(got, expected))
    return got == expected


def python_fixture(groups, marker="__MODEL_LENS_FIXTURE__"):
    blob = json.dumps(_payload(groups), ensure_ascii=True, separators=(",", ":"))
    return f"""import atexit
import contextlib
import copy
import io
import json
earned=0
group_points=[]
_finished=False
def _emit_exit():
    if not _finished:
        print({marker!r} + " POINTS " + str(earned) + "/20")
atexit.register(_emit_exit)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from solution import solve
groups = json.loads({blob!r})
def equal(a,b):
    if type(a) is not type(b): return False
    if isinstance(b,dict): return set(a)==set(b) and all(equal(a[k],v) for k,v in b.items())
    if isinstance(b,list): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b
for group in groups:
    before=earned
    for batch in group:
        ok=True
        for case in batch:
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    got = solve(copy.deepcopy(case["input"]))
                hit=equal(got,case["expected"])
            except Exception: hit=False
            ok=ok and hit
        earned+=int(ok)
    group_points.append(earned-before)
_finished=True
for i,n in enumerate(group_points): print({marker!r} + f" GROUP {{i}} {{n}}/4")
print({marker!r} + f" POINTS {{earned}}/20")
"""


def go_fixture(groups, marker="__MODEL_LENS_FIXTURE__"):
    blob = json.dumps(_payload(groups), ensure_ascii=True, separators=(",", ":"))
    # 避免模型代码和评分器共享反射比较的整数/浮点约定：两侧从 JSON 同形解码。
    return (
        """package solution
import ("encoding/json"; "fmt"; "reflect"; "testing")
func TestContent20260925(t *testing.T) {
  type Case struct { Input json.RawMessage `json:"input"`; Expected json.RawMessage `json:"expected"` }
  var groups [][][]Case
  if err := json.Unmarshal([]byte("""
        + json.dumps(blob)
        + """), &groups); err != nil { t.Fatal(err) }
  earned := 0
  groupPoints := []int{}
  for _, group := range groups { before:=earned; for _, batch := range group {
    ok := true
    for _, c := range batch {
      hit := func() (hit bool) {
        defer func(){ if recover()!=nil { hit=false } }()
        var got, want any
        if json.Unmarshal(Solve(c.Input), &got)!=nil { return false }
        if json.Unmarshal(c.Expected, &want)!=nil { return false }
        return reflect.DeepEqual(got,want)
      }()
      ok = ok && hit
    }
    if ok { earned++ }
  }; groupPoints=append(groupPoints,earned-before) }
  for i,n:=range groupPoints { fmt.Printf("%s GROUP %d %d/4\\n", """ + json.dumps(marker) + """, i,n) }
  fmt.Printf("%s POINTS %d/20\\n", """ + json.dumps(marker) + """, earned)
}
"""
    )


def ts_fixture(groups, marker="__MODEL_LENS_FIXTURE__"):
    blob = json.dumps(_payload(groups), ensure_ascii=True, separators=(",", ":"))
    return (
        """declare const require: any;
declare const process: any;
const _marker = """ + json.dumps(marker) + """;
let _finished = false;
let earned = 0;
process.on("exit", () => { if (!_finished) console.log(`${_marker} POINTS ${earned}/20`); });
const _log = console.log;
console.log = () => {};
const {solve} = require("./solution");
console.log = _log;
const groups: any = """
        + blob
        + """;
function equal(a: any,b: any): boolean {
  if (a === null || b === null) return a === b;
  if (typeof a !== typeof b) return false;
  if (Array.isArray(b)) return Array.isArray(a) && a.length===b.length && b.every((v:any,i:number)=>equal(a[i],v));
  if (typeof b === "object") return !Array.isArray(a) && Object.keys(a).length===Object.keys(b).length && Object.keys(b).every(k=>Object.prototype.hasOwnProperty.call(a,k)&&equal(a[k],b[k]));
  return a === b;
}
const groupPoints:number[]=[];
for (const group of groups) {const before=earned; for (const batch of group) {
  let ok=true;
  for (const c of batch) {
    let hit=false;
    try { const old=console.log; console.log=()=>{}; const got=solve(JSON.parse(JSON.stringify(c.input))); console.log=old; hit=equal(got, c.expected); } catch { console.log=_log; }
    ok=ok && hit;
  }
  if (ok) earned++;
} groupPoints.push(earned-before); }
_finished=true;
groupPoints.forEach((n,i)=>console.log(`${_marker} GROUP ${i} ${n}/4`));
console.log(`${_marker} POINTS ${earned}/20`);
"""
    )


def score_coding(item_id, text, language):
    item = BY_ID[item_id]
    if not item.reference:
        raise ValueError("reasoning_item")
    factories = {
        "python": (python_result_fixture, "fixture.py"),
        "go": (go_result_fixture, "fixture_test.go"),
        "typescript": (ts_result_fixture, "fixture.ts"),
    }
    if language not in factories:
        raise ValueError("language_required")
    # 一题一次只接受一份代码，防止多候选抽取顺序带来隐式多次机会。
    aliases = {
        "python": "python|py",
        "go": "go|golang",
        "typescript": "typescript|ts|tsx|javascript|js",
    }
    fences = list(re.finditer(r"```([^\n`]*)\n(.*?)```", text, re.DOTALL))
    if (
        len(fences) != 1
        or not re.fullmatch(
            aliases[language], fences[0].group(1).strip(), re.IGNORECASE
        )
        or not fences[0].group(2).strip()
    ):
        return Score(
            item_id,
            language,
            "missing",
            "missing_fence",
            None,
            20,
            None,
            None,
            [],
            False,
        )
    factory, filename = factories[language]
    marker = "__MODEL_LENS_FIXTURE_" + secrets.token_hex(12) + "__"
    groups = coding_cases(item_id)
    with tempfile.TemporaryDirectory(prefix="bank-20260925-") as temp:
        root = Path(temp)
        fixture = root / "bank" / "tests" / filename
        fixture.parent.mkdir(parents=True)
        fixture.write_text(factory(groups, marker), encoding="utf-8")
        question = Question(
            id=item_id,
            domain="coding",
            difficulty=item.level,
            prompt=item.prompt,
            grader={
                "type": "code_tests",
                "language": language,
                "tests_file": str(fixture.relative_to(root)),
                "result_marker": marker,
            },
            pass_criteria="POINTS 20/20",
            language=language,
        )
        result = grade_response(question, text, repo_root=root)
    case_score = _score_case_results(item_id, groups, result.detail, language)
    if case_score is not None:
        return case_score
    if result.status in {"missing", "error"}:
        return Score(
            item_id,
            language,
            result.status,
            "missing_toolchain" if result.status == "missing" else "runner_error",
            None,
            20,
            None,
            None,
            [],
            True,
        )
    # 现有 runner 保留部分测试点；异常退出、编译失败或缺标记统一为 0。
    points = (
        result.points if result.points_total == 20 and result.points is not None else 0
    )
    passed = result.status == "pass" and points == 20
    if passed:
        reason = "ok"
    elif "timeout" in result.detail:
        reason = "timeout"
    elif "compile" in result.detail:
        reason = "compile_error"
    elif "forbidden import" in result.detail:
        reason = "forbidden_import"
    elif result.points_total == 20:
        reason = "tests_failed"
    else:
        reason = "execution_error"
    breakdown = []
    if passed:
        breakdown = [
            {"name": name, "points": budget, "max": budget}
            for name, budget in item.groups
        ]
    elif result.points_total == 20:
        markers = re.findall(r"^GROUP ([0-4]) ([0-4])/4$", result.detail, re.MULTILINE)
        if (
            len(markers) == 5
            and [int(i) for i, _ in markers] == list(range(5))
            and sum(int(n) for _, n in markers) == points
        ):
            breakdown = [
                {"name": item.groups[int(i)][0], "points": int(n), "max": 4}
                for i, n in markers
            ]
        else:
            return Score(
                item_id,
                language,
                "fail",
                "invalid_group_report",
                0.0,
                20,
                0.0,
                False,
                [],
                True,
            )
    return Score(
        item_id,
        language,
        "pass" if passed else "fail",
        reason,
        float(points),
        20,
        points / 2,
        passed,
        breakdown,
        True,
    )
