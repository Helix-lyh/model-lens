"""Score one coding answer. No question identifiers and no report totals."""

from __future__ import annotations

import json
import secrets
import tempfile
from pathlib import Path

from .describe_contract import project_output, trace_ok, valid_document
from .score import Score
from src.grade import grade_response
from src.types import Question


def score_answer(text: str, language: str, *, item_id: str, groups, schema: dict, facts, fixture, runtime: dict | None):
    """Compare one answer with prepared cases.

    The question bank supplies `facts` and `fixture`. This loop does not
    branch on which question it is scoring.
    """
    marker = "__MODEL_LENS_FIXTURE_" + secrets.token_hex(8) + "__"
    filename = {"python": "test.py", "go": "test_test.go", "typescript": "test.ts"}[language]
    with tempfile.TemporaryDirectory(prefix="coding-score-") as temp:
        root = Path(temp)
        path = root / "bank" / "tests" / filename
        path.parent.mkdir(parents=True)
        path.write_text(fixture(schema, groups, marker, language), encoding="utf-8")
        question = Question(
            id=item_id, domain="coding", difficulty="extreme", prompt="",
            grader={"type": "code_tests", "language": language, "tests_file": str(path.relative_to(root)), "result_marker": marker, "timeout_s": 60},
            pass_criteria="20/20", language=language,
        )
        if runtime:
            question.grader["runtime_env"] = runtime
        result = grade_response(question, text, repo_root=root)
    doc = None
    saw_describe = False
    parsed = {}
    saw_case = False
    for line in result.detail.splitlines():
        if line.startswith("DESCRIBE "):
            saw_describe = True
            try:
                doc = json.loads(line.split(" ", 1)[1])
            except json.JSONDecodeError:
                doc = None
        if not line.startswith("CASE "):
            continue
        saw_case = True
        head, payload = line.split(" ", 2)[1:]
        try:
            parsed[int(head)] = json.loads(payload)
        except json.JSONDecodeError:
            parsed[int(head)] = None
    if not saw_case:
        return {"status": result.status, "points": result.points, "score10": result.score10, "passed": result.passed, "reason_code": "execution_error", "detail": result.detail}
    if not saw_describe or not valid_document(doc, schema):
        return Score(item_id, language, "fail", "describe_invalid", 0.0, 20, 0.0, False, [], True).to_dict()
    earned = 0
    offset = 0
    breakdown = []
    bound = set(schema.get("bound") or [])
    for index, group in enumerate(groups):
        points = 0
        for batch in group:
            ok = True
            for case in batch:
                got = parsed.get(offset)
                projected = project_output(got.get("output"), doc) if isinstance(got, dict) else None
                expected_facts = facts(case.expected["output"])
                try:
                    got_facts = facts(projected)
                except (TypeError, ValueError, KeyError, AttributeError):
                    got_facts = None
                ok = ok and isinstance(got, dict) and set(got) == {"trace", "output"} and trace_ok(got.get("trace"), case.expected["trace"], bound) and got_facts == expected_facts
                offset += 1
            points += int(ok)
        earned += points
        breakdown.append({"name": f"g{index + 1}", "points": points, "max": 4})
    reason = "ok" if earned == 20 else "tests_failed"
    return Score(item_id, language, "pass" if earned == 20 else "fail", reason, float(earned), 20, earned / 2, earned == 20, breakdown, True).to_dict()
