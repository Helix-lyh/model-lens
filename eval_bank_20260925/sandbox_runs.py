"""在沙箱里只收集 solve 的原始输出，判分在宿主进程完成。

被测代码和夹具在同一个解释器里，夹具里的任何判定、计分都可能被被测代码改写或伪造。
所以沙箱只做一件事：按顺序调用 solve，把输出用一条带随机 nonce 的 CASE 行写回。
宿主进程要求这条结果行恰好出现一次，再用宿主侧的判定函数计分；关系表不进沙箱。
"""
from __future__ import annotations

import json
import secrets
import tempfile
from pathlib import Path
from typing import Any

from src.grade import grade_response
from src.types import Question


def runs_fixture(nonce: str, cases: dict[str, Any]) -> str:
    blob = json.dumps(cases, ensure_ascii=False, separators=(",", ":"))
    return f'''import contextlib, copy, io, json, os
_fd = os.dup(1)
_write = os.write
_exit = os._exit
_dumps = json.dumps
CASES = json.loads({blob!r})
runs = {{}}
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from solution import solve
except BaseException:
    solve = None
for name, events in CASES.items():
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            runs[name] = solve(copy.deepcopy(events)) if solve is not None else None
    except BaseException:
        runs[name] = None
try:
    encoded = _dumps(runs, ensure_ascii=True, default=repr)
except BaseException:
    encoded = "{{}}"
_write(_fd, ({nonce!r} + " CASE 0 " + encoded + "\\n").encode())
_exit(0)
'''


def collect_runs(item_id: str, text: str, cases: dict[str, Any], *, timeout_s: float | None = None):
    """返回 (runs, unavailable)。unavailable 非空表示判分环境问题，不是模型的分。

    结果行缺失、重复或无法解析时 runs 为 {}，等于所有用例都没有输出。
    """
    nonce = "__MODEL_LENS_RUNS_" + secrets.token_hex(16) + "__"
    with tempfile.TemporaryDirectory(prefix="engineering-runs-") as directory:
        root = Path(directory)
        tests = root / "bank" / "tests"
        tests.mkdir(parents=True)
        (tests / "tests.py").write_text(runs_fixture(nonce, cases), encoding="utf-8")
        grader = {"type": "code_tests", "language": "python", "tests_file": "bank/tests/tests.py",
                  "result_marker": nonce}
        if timeout_s is not None:
            grader["timeout_s"] = timeout_s
        grade = grade_response(
            Question(id=item_id, domain="engineering", difficulty="extreme", prompt="",
                     grader=grader,
                     pass_criteria="host-judged", language="python"),
            text, repo_root=root,
        )
    from .evaluation import unjudged_execution
    unavailable = unjudged_execution(grade)
    if unavailable is not None:
        return {}, unavailable
    lines = [line for line in (grade.detail or "").splitlines() if line.startswith("CASE ")]
    if len(lines) != 1:
        return {}, None
    try:
        runs = json.loads(lines[0].split(" ", 2)[2])
    except (ValueError, IndexError):
        return {}, None
    return (runs if isinstance(runs, dict) else {}), None
