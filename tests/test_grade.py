from __future__ import annotations

from pathlib import Path

from src.bank import load_questions, repo_root
from src.grade import (
    extract_first_python_fence,
    extract_structure_payload,
    grade_response,
    parse_points,
    run_sandbox,
)
from src.types import Question


def test_extract_labeled_fence() -> None:
    text = "好的\n```python\ndef f():\n    return 1\n```\n完"
    assert extract_first_python_fence(text) == "def f():\n    return 1"


def test_extract_missing() -> None:
    assert extract_first_python_fence("没有代码") is None
    assert extract_first_python_fence("```json\n{}\n```") is None


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
    assert set(by_id) == {"knowledge-easy-01", "knowledge-easy-02", "knowledge-easy-03", "knowledge-medium-01", "knowledge-medium-02", "knowledge-medium-03", "knowledge-hard-01", "knowledge-hard-02"}
    expect = {
        "knowledge-easy-01": ("0", "7"),
        "knowledge-easy-02": ("地面", "空中"),
        "knowledge-medium-01": ("不扳", "扳"),
        "knowledge-easy-03": ("0", "50"),
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
    }
    for qid, payload in good.items():
        boxed = f"```json\n{payload}\n```" if qid != "knowledge-medium-02" else f"```text\n{payload}\n```"
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


def test_coding_missing_without_fence() -> None:
    q = next(x for x in load_questions() if x.id == "coding-medium-01")
    assert q.id == "coding-medium-01"
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
        "assert apply_ops([]) == {'A': 0, 'B': 0, 'C': 0}\n",
        encoding="utf-8",
    )
    status, detail = run_sandbox(_SHELF, spy)
    assert status == "pass", detail


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
