from __future__ import annotations

from src.bank import load_questions, run_bank, salt_prompt, select_questions
from src.types import CompletionRecord, Endpoint


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
    assert 20 <= len(qs) <= 60
    assert {q.domain for q in qs} == {"architecture", "coding", "knowledge"}
    assert {q.difficulty for q in qs} == {"easy", "medium", "hard"}
    for q in qs:
        domain, diff, _seq = q.id.split("-")
        assert domain == q.domain
        assert diff == q.difficulty
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
    assert "think_penalty" in result.questions[0].samples[0].detail


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

    qs = [q for q in load_questions() if q.id == "coding-medium-01"]
    result = run_bank(Boom(), qs, salt="t", quick=True)
    assert result.questions[0].samples[0].status == "missing"
    assert result.domain_pass0["coding"]["judged"] == 0
    assert result.domain_pass0["coding"]["missing"] == 1
