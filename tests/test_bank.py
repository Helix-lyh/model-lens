from __future__ import annotations

import threading

import pytest

from collections import Counter

from src.bank import (
    BANK_EXPANDED_COUNT,
    BANK_QUICK_COUNT,
    BANK_RAW_COUNT,
    DIFFICULTIES,
    DOMAINS,
    RAW_MATRIX,
    _expand_question,
    _group_stats,
    _majority,
    _summarize_bank,
    _validate_bank,
    load_questions,
    run_bank,
    salt_prompt,
    select_questions,
)
from src.types import CompletionRecord, Question, QuestionResult, SampleGrade


class FakeClient:
    def __init__(self, answers: dict[str, str]):
        self.answers = answers
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def complete(self, messages, *, temperature=0.0, max_tokens=1, kind="chat", stream=False):
        rec = {
            "kind": kind,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "content": messages[0]["content"],
            "stream": stream,
        }
        with self._lock:
            self.calls.append(rec)
        qid = kind.split(":")[1]
        text = self.answers.get(qid, "")
        return CompletionRecord(
            kind=kind,
            endpoint="https://example.test/v1",
            model="demo",
            request={"messages": messages},
            status_code=200,
            latency_ms=1,
            prompt_tokens=10,
            completion_tokens=5,
            content=text,
        )


def _raw_id(question) -> str:
    if question.language:
        return question.id.rsplit("-", 1)[0]
    return question.id


def test_load_questions_size_and_ids() -> None:
    qs = load_questions()
    raw_ids = {_raw_id(q) for q in qs}
    assert 20 <= len(raw_ids) <= 60
    assert {q.domain for q in qs} == set(DOMAINS)
    assert {q.difficulty for q in qs} == set(DIFFICULTIES)
    for q in qs:
        parts = q.id.split("-")
        assert parts[0] == q.domain
        assert parts[1] == q.difficulty
        if q.domain == "coding":
            assert parts[-1] in {"python", "go", "typescript"}
            assert q.language == parts[-1]
    coding = [q for q in qs if q.domain == "coding"]
    assert len(coding) == 36
    assert {q.language for q in coding} == {"python", "go", "typescript"}
    assert len(raw_ids) == BANK_RAW_COUNT
    assert len(qs) == BANK_EXPANDED_COUNT
    raw_counts = Counter(_raw_id(q) for q in qs)
    assert sum(1 for q in qs if q.domain == "coding" and q.language) == 36
    assert all(count == 3 for qid, count in raw_counts.items() if qid.startswith("coding-"))
    raw_domains: Counter[str] = Counter()
    seen: set[str] = set()
    for q in qs:
        rid = _raw_id(q)
        if rid in seen:
            continue
        seen.add(rid)
        raw_domains[q.domain] += 1
    assert dict(raw_domains) == {domain: sum(RAW_MATRIX[domain].values()) for domain in DOMAINS}
    quick = select_questions(qs, "quick")
    full = select_questions(qs, "full")
    assert all(q.difficulty in {"easy", "medium"} for q in quick)
    assert len(full) == len(qs)
    assert len(quick) == BANK_QUICK_COUNT
    assert len(quick) < len(full)
    assert load_questions(mode="quick") == quick


def test_salt_prefix_unrelated() -> None:
    out = salt_prompt("只输出整数。", "run-1")
    assert out.startswith("【审计标记 run-1")
    assert "只输出整数" in out


def test_quick_skips_hard() -> None:
    qs = load_questions()
    client = FakeClient({})
    result = run_bank(client, qs, salt="t", quick=True)
    assert result.n_questions == sum(1 for q in qs if q.difficulty in {"easy", "medium"})
    assert all(q.difficulty in {"easy", "medium"} for q in result.questions)
    assert not any(c["kind"].split(":")[1].split("-")[1] == "hard" for c in client.calls)


def test_quick_one_sample_and_knowledge_alarm() -> None:
    qs = [q for q in load_questions() if q.domain == "knowledge"]
    client = FakeClient({})
    result = run_bank(client, qs, salt="t", quick=True)
    assert result.quick is True
    assert all(q.difficulty in {"easy", "medium"} for q in result.questions)
    assert result.n_questions == len(result.questions)
    assert all(len(q.samples) == 1 for q in result.questions)
    assert result.knowledge_all_wrong is True
    assert result.knowledge_alarm


def test_reasoning_all_wrong_does_not_trip_knowledge_alarm() -> None:
    qs = [q for q in load_questions() if q.domain == "reasoning"]
    result = run_bank(FakeClient({}), qs, salt="t", quick=True)
    assert result.domain_pass0["reasoning"]["judged"] == sum(
        1 for q in qs if q.difficulty in {"easy", "medium"}
    )
    assert result.knowledge_all_wrong is False
    assert result.knowledge_alarm is None


def test_full_mode_four_samples() -> None:
    qs = [q for q in load_questions() if q.id == "knowledge-easy-01"]
    client = FakeClient({"knowledge-easy-01": "711.90"})
    result = run_bank(client, qs, salt="t", quick=False)
    assert len(result.questions[0].samples) == 4
    assert result.questions[0].pass0 is True
    assert result.questions[0].majority is True
    assert result.questions[0].score10 == 10.0
    assert result.domain_points["knowledge"]["score10"] == 10.0
    assert all(c["content"].startswith("【审计标记") for c in client.calls)
    assert all(c["stream"] is False for c in client.calls)


def test_stream_metrics_flag_forwarded() -> None:
    qs = [q for q in load_questions() if q.id == "knowledge-easy-01"]
    client = FakeClient({"knowledge-easy-01": "711.90"})
    run_bank(client, qs, salt="t", quick=True, stream_metrics=True)
    assert client.calls[0]["stream"] is True


def test_think_penalty_halves_easy_score() -> None:
    qs = [q for q in load_questions() if q.id == "knowledge-easy-01"]
    client = FakeClient({"knowledge-easy-01": "711.90"})

    def _wrap(*args, **kwargs):
        rec = FakeClient.complete(client, *args, **kwargs)
        rec.completion_tokens = 90_000
        return rec

    client.complete = _wrap  # type: ignore[method-assign]
    result = run_bank(client, qs, salt="t", quick=True)
    assert result.questions[0].pass0 is True
    assert result.questions[0].score10 == 5.0
    sample = result.questions[0].samples[0]
    assert sample.points == 1
    assert sample.points_total == 2
    assert result.domain_points["knowledge"]["earned"] == 1
    assert result.domain_points["knowledge"]["total"] == 2
    assert result.domain_points["knowledge"]["score10"] == 5.0
    assert "think_penalty" in sample.detail


def test_http_error_is_missing_not_abort() -> None:
    class Boom:
        def complete(self, messages, *, stream=False, **kwargs):
            return CompletionRecord(
                kind=kwargs.get("kind", "x"),
                endpoint="e",
                model="m",
                request={},
                status_code=500,
                latency_ms=1,
                prompt_tokens=None,
                completion_tokens=None,
                content=None,
                error="HTTP 500",
            )

    qs = [q for q in load_questions() if q.id == "coding-medium-01-python"]
    result = run_bank(Boom(), qs, salt="t", quick=True)
    assert result.questions[0].samples[0].status == "missing"
    assert result.domain_pass0["coding"]["judged"] == 0
    assert result.domain_pass0["coding"]["missing"] == 1


def test_expand_code_tests_requires_all_languages() -> None:
    q = Question(
        id="coding-easy-99",
        domain="coding",
        difficulty="easy",
        prompt="x",
        grader={
            "type": "code_tests",
            "languages": {
                "python": {"tests_file": "bank/tests/b01_shelf.py"},
                "go": {"tests_file": "bank/tests/go/apply_ops_test.go"},
            },
        },
        pass_criteria="t",
    )
    with pytest.raises(ValueError, match="typescript"):
        _expand_question(q)


def test_validate_bank_counts_pre_expand() -> None:
    base = load_questions()
    raw = []
    seen: set[str] = set()
    for q in base:
        rid = _raw_id(q)
        if rid in seen:
            continue
        seen.add(rid)
        raw.append(
            Question(
                id=rid,
                domain=q.domain,
                difficulty=q.difficulty,
                prompt=q.prompt,
                grader={"type": "alias", "answers": ["0"]},
                pass_criteria="t",
            )
        )
    with pytest.raises(ValueError, match="展开前"):
        _validate_bank(raw[:19])


def test_expand_code_tests_requires_languages() -> None:
    q = Question(
        id="coding-easy-99",
        domain="coding",
        difficulty="easy",
        prompt="x",
        grader={"type": "code_tests", "tests_file": "bank/tests/b01_shelf.py"},
        pass_criteria="t",
    )
    with pytest.raises(ValueError, match="languages"):
        _expand_question(q)


def test_majority_missing_is_none() -> None:
    missing = SampleGrade(temperature=0.0, status="missing", passed=None, detail="x")
    fail = SampleGrade(temperature=0.0, status="fail", passed=False, detail="x")
    ok = SampleGrade(temperature=0.0, status="pass", passed=True, detail="x")
    assert _majority([missing, missing, missing, missing]) is None
    assert _majority([fail, fail, missing, missing]) is None
    assert _majority([ok, ok, ok, missing]) is True
    assert _majority([ok, fail, fail, fail]) is False


def test_run_bank_concurrency_keeps_question_order() -> None:
    qs = [q for q in load_questions() if q.domain == "knowledge" and q.difficulty == "easy"]
    client = FakeClient({q.id: "711.90" for q in qs})
    result = run_bank(client, qs, salt="t", quick=True, concurrency=4)
    assert [q.question_id for q in result.questions] == [q.id for q in qs]
    assert len(client.calls) == len(qs)
    assert result.n_questions == len(qs)


def test_extreme_think_penalty_preserves_pass_and_doubles_total() -> None:
    q = next(q for q in load_questions() if q.id == "knowledge-extreme-01")
    answer = (
        '```json\n{"load_kwh":2.1,"battery_kwh":2.4,'
        '"days_supported":1.029,"status":"ONE_DAY"}\n```'
    )
    client = FakeClient({q.id: answer})

    def _wrap(*args, **kwargs):
        rec = FakeClient.complete(client, *args, **kwargs)
        rec.completion_tokens = 170_000
        return rec

    client.complete = _wrap  # type: ignore[method-assign]
    result = run_bank(client, [q], salt="t", quick=False)
    sample = result.questions[0].samples[0]
    assert sample.passed is True
    assert sample.score10 == 5.0
    assert sample.points == 5
    assert sample.points_total == 10
    assert "think_penalty" in sample.detail


def _variant_result(
    cluster: str,
    language: str,
    passed: bool | None,
    *,
    majority: bool | None = None,
    points: int | None = None,
    points_total: int | None = None,
    score10: float | None = None,
) -> QuestionResult:
    status = "pass" if passed is True else "fail" if passed is False else "missing"
    sample = SampleGrade(
        temperature=0.0,
        status=status,
        passed=passed,
        detail="x",
        points=points,
        points_total=points_total,
        score10=score10,
    )
    return QuestionResult(
        question_id=f"{cluster}-{language}",
        domain="coding",
        difficulty="hard",
        samples=[sample],
        pass0=passed,
        majority=majority,
        score10=score10,
    )


def test_coding_cluster_summary_keeps_fractional_points_and_strict_denominator() -> None:
    items = [
        _variant_result("coding-hard-01", "python", True, majority=True, points=1, points_total=3, score10=3.33),
        _variant_result("coding-hard-01", "go", True, majority=True, points=2, points_total=3, score10=6.67),
        _variant_result("coding-hard-01", "typescript", None),
        _variant_result("coding-hard-02", "python", False, majority=False, points=0, points_total=3, score10=0.0),
        _variant_result("coding-hard-02", "go", True, majority=True, points=3, points_total=3, score10=10.0),
        _variant_result("coding-hard-02", "typescript", True, majority=True, points=3, points_total=3, score10=10.0),
    ]
    available = _group_stats(items)
    strict = _group_stats(items, strict_coding=True)
    assert available == {
        "passed": 1,
        "judged": 2,
        "missing": 0,
        "earned": 3.5,
        "total": 6.0,
        "score10": 5.83,
    }
    assert strict == {
        "passed": 0,
        "judged": 1,
        "missing": 1,
        "earned": 2.0,
        "total": 3.0,
        "score10": 6.67,
    }
    summary = _summarize_bank(items, salt="t", quick=True)
    assert summary.coding_available["judged"] == 2
    assert summary.coding_strict["judged"] == 1
    assert summary.domain_points["coding"]["earned"] == 3.5
    assert summary.domain_points["coding"]["total"] == 6.0
