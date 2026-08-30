from __future__ import annotations

import pytest

from src.bank import _expand_question, _majority, load_questions, run_bank, salt_prompt, select_questions
from src.types import CompletionRecord, Question, SampleGrade


class FakeClient:
    def __init__(self, answers: dict[str, str]):
        self.answers = answers
        self.calls: list[dict] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=1, kind="chat", stream=False):
        self.calls.append(
            {
                "kind": kind,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "content": messages[0]["content"],
                "stream": stream,
            }
        )
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


def test_load_questions_size_and_ids() -> None:
    qs = load_questions()
    raw_count = len([q for q in qs if q.language in (None, "python")])
    assert 20 <= raw_count <= 60
    assert {q.domain for q in qs} == {"architecture", "coding", "knowledge", "reasoning"}
    assert {q.difficulty for q in qs} == {"easy", "medium", "hard"}
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
    assert raw_count == 48
    assert len(qs) == 72
    quick = select_questions(qs, "quick")
    full = select_questions(qs, "full")
    assert all(q.difficulty in {"easy", "medium"} for q in quick)
    assert len(full) == len(qs)
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


def test_full_mode_four_samples() -> None:
    qs = [q for q in load_questions() if q.id == "knowledge-easy-01"]
    client = FakeClient({"knowledge-easy-01": "0"})
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
    client = FakeClient({"knowledge-easy-01": "0"})
    run_bank(client, qs, salt="t", quick=True, stream_metrics=True)
    assert client.calls[0]["stream"] is True


def test_think_penalty_halves_easy_score() -> None:
    qs = [q for q in load_questions() if q.id == "knowledge-easy-01"]
    client = FakeClient({"knowledge-easy-01": "0"})

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
