from __future__ import annotations

from pathlib import Path

import pytest

from src.bank import load_questions, repo_root
from src.grade import (
    _forbidden_import,
    extract_fenced_code,
    extract_structure_payload,
    grade_response,
    parse_points,
    run_go_sandbox,
    run_sandbox,
    run_ts_sandbox,
)
from src.toolchain import Tool, Toolchain, discover
from src.types import Question


def test_extract_labeled_fence() -> None:
    text = "好的\n```python\ndef f():\n    return 1\n```\n完"
    assert extract_fenced_code(text, "python") == "def f():\n    return 1"


def test_extract_missing() -> None:
    assert extract_fenced_code("没有代码", "python") is None
    assert extract_fenced_code("```json\n{}\n```", "python") is None


def test_keyword_grader() -> None:
    q = Question(
        id="architecture-easy-00",
        domain="architecture",
        difficulty="easy",
        prompt="x",
        grader={
            "type": "keyword",
            "min_hits": 2,
            "must_include": [["幂等", "去重"], ["队列", "mq"]],
        },
        pass_criteria="t",
    )
    ok = grade_response(q, "用消息队列异步，消费者必须幂等", repo_root=repo_root())
    assert ok.status == "pass"
    assert ok.points == 2 and ok.points_total == 2
    assert ok.score10 == 10.0
    bad = grade_response(q, "我觉得可以微服务", repo_root=repo_root())
    assert bad.status == "fail"
    assert bad.score10 == 0.0
    fluff = Question(
        id="architecture-easy-00",
        domain="architecture",
        difficulty="easy",
        prompt="x",
        grader={
            "type": "keyword",
            "min_hits": 2,
            "must_include": [["幂等", "去重"], ["队列", "mq"]],
            "must_exclude": [["综上所述"]],
        },
        pass_criteria="t",
    )
    dumped = grade_response(
        fluff, "用消息队列异步，消费者必须幂等。综上所述。", repo_root=repo_root()
    )
    assert dumped.status == "fail"
    assert dumped.points == 2


def test_alias_grader() -> None:
    q = Question(
        id="knowledge-easy-00",
        domain="knowledge",
        difficulty="easy",
        prompt="x",
        grader={"type": "alias", "answers": ["H2O", "h2o"]},
        pass_criteria="t",
    )
    assert grade_response(q, "答案是 H2O。", repo_root=repo_root()).status == "pass"
    assert grade_response(q, "H₂O", repo_root=repo_root()).status == "pass"
    assert grade_response(q, "不知道", repo_root=repo_root()).status == "fail"


def test_knowledge_trap_canonical_and_intuition() -> None:
    by_id = {q.id: q for q in load_questions() if q.domain == "knowledge"}
    assert set(by_id) == {
        "knowledge-easy-01",
        "knowledge-easy-02",
        "knowledge-easy-03",
        "knowledge-easy-04",
        "knowledge-medium-01",
        "knowledge-medium-02",
        "knowledge-medium-03",
        "knowledge-medium-04",
        "knowledge-hard-01",
        "knowledge-hard-02",
        "knowledge-hard-03",
        "knowledge-hard-04",
    }
    expect = {
        "knowledge-easy-01": ("0", "7"),
        "knowledge-easy-02": ("地面", "空中"),
        "knowledge-medium-01": ("不扳", "扳"),
        "knowledge-easy-03": ("0", "50"),
        "knowledge-easy-04": ("一样重", "铁"),
        "knowledge-medium-04": ("更低", "相同"),
    }
    for qid, (good, bad) in expect.items():
        q = by_id[qid]
        assert grade_response(q, good, repo_root=repo_root()).passed is True
        assert grade_response(q, bad, repo_root=repo_root()).passed is False
        assert grade_response(q, f"答案是 {good}", repo_root=repo_root()).passed is False


def test_structure_follow_pass_and_fail() -> None:
    assert extract_structure_payload("```json\n{}\n```") == "{}"
    by_id = {q.id: q for q in load_questions() if q.domain == "knowledge"}
    good = {
        "knowledge-hard-01": '{"root":{"ok":{"ok":{"ok":{"0k":{"ok":{"tip":42,"_":[0,null,false]}}}}}}}',
        "knowledge-medium-02": "<<HEAD>>\ndrahcro\n7\ndra*cro\n<<TAIL>>",
        "knowledge-hard-02": '[{"i":0,"sq":0,"mark":"n"},{"i":1,"sq":1,"mark":"n"},{"i":2,"sq":4,"mark":"n"},null,{"i":4,"sq":16,"mark":"n"},{"i":5,"sq":25,"mark":"N"}]',
        "knowledge-medium-03": '{"z":{"z":{"z":"ok"}},"a":[],"z2":-0}',
        "knowledge-hard-03": "[[v2]]\nsgnl\nsgnl-sgnl\n9\nlngs\n[[end]]",
        "knowledge-hard-04": '{"data":["0",0,false,null],"meta":{"v":1e2,"k k":{}}}',
    }
    text_payloads = {"knowledge-medium-02", "knowledge-hard-03"}
    for qid, payload in good.items():
        boxed = f"```text\n{payload}\n```" if qid in text_payloads else f"```json\n{payload}\n```"
        grade = grade_response(by_id[qid], boxed, repo_root=repo_root())
        assert grade.passed is True, (qid, grade.detail)
        assert grade.score10 == 10.0
        bad = grade_response(by_id[qid], "```json\n{}\n```", repo_root=repo_root())
        assert bad.passed is False
        assert bad.points is not None and bad.points < bad.points_total


def test_alias_exact_and_latex() -> None:
    q = Question(
        id="knowledge-easy-00",
        domain="knowledge",
        difficulty="easy",
        prompt="x",
        grader={"type": "alias", "match": "exact", "answers": ["3x10^5", "101"]},
        pass_criteria="t",
    )
    assert grade_response(q, "3\\times10^5", repo_root=repo_root()).status == "pass"
    assert grade_response(q, "101", repo_root=repo_root()).status == "pass"
    assert grade_response(q, "状态码是 101", repo_root=repo_root()).status == "fail"


def test_code_tests_without_language_is_error() -> None:
    q = Question(
        id="coding-easy-00",
        domain="coding",
        difficulty="easy",
        prompt="x",
        grader={"type": "code_tests", "tests_file": "bank/tests/b01_shelf.py", "language": "python"},
        pass_criteria="t",
    )
    grade = grade_response(q, "```python\ndef f():\n    return 1\n```", repo_root=repo_root())
    assert grade.status == "error"
    assert grade.passed is None
    assert "language" in grade.detail


def test_python_tests_type_is_unknown() -> None:
    q = Question(
        id="coding-easy-00",
        domain="coding",
        difficulty="easy",
        prompt="x",
        grader={"type": "python_tests", "tests_file": "bank/tests/b01_shelf.py"},
        pass_criteria="t",
        language="python",
    )
    grade = grade_response(q, "```python\npass\n```", repo_root=repo_root())
    assert grade.status == "error"
    assert "unknown grader" in grade.detail


def test_coding_missing_without_fence() -> None:
    q = next(x for x in load_questions() if x.id == "coding-medium-01-python")
    assert q.id == "coding-medium-01-python"
    assert q.language == "python"
    grade = grade_response(q, "我可以写 two sum", repo_root=repo_root())
    assert grade.status == "missing"
    assert grade.passed is None
    assert grade.score10 is None


_SHELF = """
def apply_ops(ops):
    bins = {"A": 0, "B": 0, "C": 0}
    nxt = {"A": "B", "B": "C", "C": "A"}
    for raw in ops:
        parts = raw.split()
        kind = parts[0]
        if kind == "+":
            bins[parts[1]] += int(parts[2])
        elif kind == "-":
            x, n = parts[1], int(parts[2])
            if bins[x] >= n:
                bins[x] -= n
        elif kind == ">":
            x, y = parts[1], parts[2]
            bins[y] += bins[x]
            bins[x] = 0
        elif kind == "?":
            x = parts[1]
            if bins[x] > 0:
                bins[x] -= 1
                bins[nxt[x]] += 1
    return bins
"""


def test_parse_points() -> None:
    assert parse_points("ok\nPOINTS 3/6\n") == (3, 6)
    assert parse_points("no points") is None
    assert parse_points("POINTS 9/9\nPOINTS 3/6\n") == (3, 6)
    assert parse_points("POINTS 5/5\nPASS\n") == (5, 5)


def test_sandbox_shelf_pass() -> None:
    status, detail = run_sandbox(_SHELF, repo_root() / "bank/tests/b01_shelf.py")
    assert status == "pass"
    assert detail == "POINTS 6/6"


def test_sandbox_shelf_partial() -> None:
    code = '''
def apply_ops(ops):
    return {"A": 0, "B": 0, "C": 0}
'''
    status, detail = run_sandbox(code, repo_root() / "bank/tests/b01_shelf.py")
    assert status == "fail"
    assert "POINTS 1/6" in detail


def test_sandbox_clears_api_keys(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TARGET_KEY", "sk-should-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-also-hidden")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bedrock-should-not-leak")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake-adc.json")
    status, detail = run_sandbox(_SHELF, repo_root() / "bank/tests/b01_shelf.py")
    assert status == "pass"
    spy = tmp_path / "spy.py"
    spy.write_text(
        "import os\n"
        "assert 'TARGET_KEY' not in os.environ\n"
        "assert 'OPENAI_API_KEY' not in os.environ\n"
        "assert 'AWS_BEARER_TOKEN_BEDROCK' not in os.environ\n"
        "assert 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ\n"
        "from solution import apply_ops\n"
        "assert apply_ops([]) == {'A': 0, 'B': 0, 'C': 0}\n"
        "print('POINTS 1/1')\n",
        encoding="utf-8",
    )
    status, detail = run_sandbox(_SHELF, spy)
    assert status == "pass", detail


def test_sandbox_exit0_without_points_fails(tmp_path: Path) -> None:
    spy = tmp_path / "spy.py"
    spy.write_text("print('ok')\n", encoding="utf-8")
    status, detail = run_sandbox("x = 1\n", spy)
    assert status == "fail"
    assert "sandbox ok" not in detail
    assert "POINTS" not in detail or "no POINTS" in detail


def test_sandbox_ignores_points_on_stderr(tmp_path: Path) -> None:
    spy = tmp_path / "spy.py"
    spy.write_text(
        "import sys\n"
        "print('POINTS 9/9', file=sys.stderr)\n"
        "print('ok')\n",
        encoding="utf-8",
    )
    status, detail = run_sandbox("x = 1\n", spy)
    assert status == "fail"
    assert detail != "POINTS 9/9"


def test_sandbox_uses_last_stdout_points(tmp_path: Path) -> None:
    spy = tmp_path / "spy.py"
    spy.write_text("print('POINTS 9/9')\nprint('POINTS 3/6')\n", encoding="utf-8")
    status, detail = run_sandbox("x = 1\n", spy)
    assert status == "fail"
    assert "POINTS 3/6" in detail
    assert parse_points(detail) == (3, 6)


def test_sandbox_blocks_network() -> None:
    code = """
def apply_ops(ops):
    import socket
    socket.create_connection(('example.com', 80), timeout=1)
    return {"A": 0, "B": 0, "C": 0}
"""
    status, detail = run_sandbox(code, repo_root() / "bank/tests/b01_shelf.py")
    assert status == "fail"
    assert "network disabled" in detail or "OSError" in detail or "POINTS 0/6" in detail


def test_sandbox_blocks_subprocess() -> None:
    code = """
def apply_ops(ops):
    import subprocess
    subprocess.run(["echo", "leak"], check=False)
    return {"A": 0, "B": 0, "C": 0}
"""
    status, detail = run_sandbox(code, repo_root() / "bank/tests/b01_shelf.py")
    assert status == "fail"
    assert "subprocess disabled" in detail or "POINTS 0/6" in detail


def test_extract_go_and_ts_fences() -> None:
    go = "好的\n```go\npackage solution\nfunc PackRuns(xs []int) [][2]int { return nil }\n```\n"
    ts = "```typescript\nexport function packRuns(xs: number[]) { return []; }\n```"
    assert extract_fenced_code(go, "go") is not None
    assert "PackRuns" in (extract_fenced_code(go, "go") or "")
    assert extract_fenced_code(ts, "typescript") is not None
    assert extract_fenced_code("没有代码", "go") is None
    assert extract_fenced_code("```python\ndef f():\n    pass\n```", "go") is None
    js = "```javascript\nexport function packRuns(xs) { return []; }\n```"
    assert extract_fenced_code(js, "typescript") is not None


_GO_PACK = """
package solution

func PackRuns(xs []int) [][2]int {
    if len(xs) == 0 {
        return nil
    }
    out := make([][2]int, 0)
    cur, cnt := xs[0], 1
    for i := 1; i < len(xs); i++ {
        if xs[i] == cur {
            cnt++
        } else {
            out = append(out, [2]int{cur, cnt})
            cur, cnt = xs[i], 1
        }
    }
    return append(out, [2]int{cur, cnt})
}
"""

_TS_PACK = """
export function packRuns(xs: number[]): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  if (xs.length === 0) return out;
  let cur = xs[0], cnt = 1;
  for (let i = 1; i < xs.length; i++) {
    if (xs[i] === cur) cnt++;
    else { out.push([cur, cnt]); cur = xs[i]; cnt = 1; }
  }
  out.push([cur, cnt]);
  return out;
}
"""


@pytest.mark.skipif(not discover().go.ok, reason="go not installed")
def test_go_sandbox_pack_runs() -> None:
    status, detail = run_go_sandbox(_GO_PACK, repo_root() / "bank/tests/go/pack_runs_test.go")
    assert status == "pass", detail
    assert detail == "POINTS 5/5"
    bad, bad_detail = run_go_sandbox(
        "package solution\nfunc PackRuns(xs []int) [][2]int { return nil }\n",
        repo_root() / "bank/tests/go/pack_runs_test.go",
    )
    assert bad == "fail"
    assert "POINTS 1/5" in bad_detail
    broken, broken_detail = run_go_sandbox("package main\nfunc main() {}\n", repo_root() / "bank/tests/go/pack_runs_test.go")
    assert broken == "fail"
    assert "POINTS" not in broken_detail or "compile" in broken_detail.lower() or "undefined" in broken_detail.lower() or "package" in broken_detail.lower()


@pytest.mark.skipif(not discover().node.ok, reason="node not installed")
def test_ts_sandbox_pack_runs() -> None:
    status, detail = run_ts_sandbox(_TS_PACK, repo_root() / "bank/tests/ts/pack_runs.ts")
    assert status == "pass", detail
    assert detail == "POINTS 5/5"
    fail_status, fail_detail = run_ts_sandbox(
        "export function packRuns(_xs: number[]): Array<[number, number]> { return []; }\n",
        repo_root() / "bank/tests/ts/pack_runs.ts",
    )
    assert fail_status == "fail"
    assert "POINTS 1/5" in fail_detail
    broken, broken_detail = run_ts_sandbox("const x = ;\n", repo_root() / "bank/tests/ts/pack_runs.ts")
    assert broken == "fail"
    assert "compile failed" in broken_detail


def test_grade_go_and_ts_questions() -> None:
    by_id = {q.id: q for q in load_questions() if q.domain == "coding"}
    go_q = by_id["coding-easy-01-go"]
    ts_q = by_id["coding-easy-01-typescript"]
    assert go_q.language == "go"
    assert "package solution" in go_q.prompt
    assert "packRuns" in ts_q.prompt
    missing_go = grade_response(go_q, "我可以写 two sum", repo_root=repo_root())
    assert missing_go.status == "missing"
    if discover().go.ok:
        ok = grade_response(go_q, f"```go\n{_GO_PACK}\n```", repo_root=repo_root())
        assert ok.status == "pass", ok.detail
        assert ok.score10 == 10.0
    if discover().node.ok:
        ok_ts = grade_response(ts_q, f"```typescript\n{_TS_PACK}\n```", repo_root=repo_root())
        assert ok_ts.status == "pass", ok_ts.detail
        assert ok_ts.score10 == 10.0


def _empty_tools() -> Toolchain:
    return Toolchain(
        python=Tool("python", "/usr/bin/python3", argv=("/usr/bin/python3",), version="Python 3.11.0"),
        go=Tool("go", None),
        node=Tool("node", None),
        tsc=Tool("tsc", None),
    )


def test_toolchain_missing_is_missing_not_zero(monkeypatch) -> None:
    monkeypatch.setattr("src.grade.discover", _empty_tools)
    q = next(x for x in load_questions() if x.id == "coding-easy-01-go")
    grade = grade_response(
        q,
        "```go\npackage solution\nfunc PackRuns(xs []int) [][2]int { return nil }\n```",
        repo_root=repo_root(),
    )
    assert grade.status == "missing"
    assert grade.passed is None
    assert grade.score10 is None
    assert "toolchain missing" in grade.detail


@pytest.mark.skipif(not discover().go.ok, reason="go not installed")
def test_forbidden_go_import_scores_zero() -> None:
    q = next(x for x in load_questions() if x.id == "coding-easy-01-go")
    text = "```go\npackage solution\nimport \"net/http\"\nfunc PackRuns(xs []int) [][2]int { return nil }\n```"
    grade = grade_response(q, text, repo_root=repo_root())
    assert grade.status == "fail"
    assert grade.passed is False
    assert grade.score10 == 0.0
    assert "forbidden import" in grade.detail


def test_forbidden_imports_cover_alias_group_and_dynamic() -> None:
    assert _forbidden_import('import net "net"\n', "go") == "net"
    assert _forbidden_import('import ("net")\n', "go") == "net"
    assert _forbidden_import('import (\n\t"net/http"\n)\n', "go") == "net/http"
    assert _forbidden_import('import (\n\thttplib "net/http"\n)\n', "go") == "net/http"
    assert _forbidden_import('import (\n\t"os/exec"\n)\n', "go") == "os/exec"
    assert _forbidden_import('import "plugin"\n', "go") == "plugin"
    assert _forbidden_import("import fs from 'fs/promises'\n", "typescript")
    assert _forbidden_import("from 'node:fs'\n", "typescript")
    assert _forbidden_import("const x = require('child_process')\n", "typescript")
    assert _forbidden_import("await import('net')\n", "typescript")
    assert _forbidden_import("import http from 'https'\n", "typescript")
    assert _forbidden_import("import d from 'dgram'\n", "typescript")
    assert _forbidden_import('import "fmt"\n', "go") is None
    assert _forbidden_import("import fs from 'path'\n", "typescript") is None
