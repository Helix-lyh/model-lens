"""L2 wrapper 离线单测：假 client / 假 vocab，不打网。"""

from __future__ import annotations

import threading

from src.types import Completer, CompletionRecord
from src.wrapper import DEFAULT_WRAPPER_TEXTS, format_wrapper_line, run_wrapper

TEXTS = ["aa", "bbbb", "cccccc", "dddddddd"]


class FakeVocab:
    def __init__(self, id: str, table: dict[str, int]):
        self.id = id
        self.table = table

    def encode_len(self, text: str, *, escaped: bool = False) -> int:
        del escaped
        return self.table[text]

    def n_hat(self, base: str, probe: str, *, escaped: bool = False) -> int:
        return self.encode_len(base + probe, escaped=escaped) - self.encode_len(
            base, escaped=escaped
        )


class FakeClient:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        extra: dict | None = None,
        kind: str = "chat",
        stream: bool = False,
    ) -> CompletionRecord:
        del extra
        text = messages[0]["content"]
        with self._lock:
            self.calls.append(
                {
                    "text": text,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "kind": kind,
                    "stream": stream,
                }
            )
        spec = self.responses.get(text, {})
        prompt_tokens = spec.get("prompt_tokens")
        if "usage" in spec:
            usage = spec["usage"]
        elif type(prompt_tokens) is int:
            usage = {"prompt_tokens": prompt_tokens}
        else:
            usage = None
        return CompletionRecord(
            kind=kind,
            endpoint="fake",
            model="fake",
            request={
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            },
            status_code=spec.get("status_code", 200),
            latency_ms=0,
            prompt_tokens=prompt_tokens,
            completion_tokens=1,
            content="",
            usage=usage,
        )


def _client_for(texts: list[str], prompt_tokens: list[int]) -> FakeClient:
    return FakeClient(
        {text: {"prompt_tokens": n, "status_code": 200} for text, n in zip(texts, prompt_tokens, strict=True)}
    )


def test_constant_plus_36():
    glm = {t: i + 1 for i, t in enumerate(TEXTS)}
    qwen = {t: (i + 1) * 4 for i, t in enumerate(TEXTS)}
    api = [glm[t] + 36 for t in TEXTS]
    catalog = {
        "glm5": FakeVocab("glm5", glm),
        "qwen2_5": FakeVocab("qwen2_5", qwen),
    }
    client = _client_for(TEXTS, api)

    result = run_wrapper(client, catalog, TEXTS)

    assert result.status == "constant"
    assert result.catalog_id == "glm5"
    assert result.value == 36
    assert result.spread == 0
    assert result.untrusted_reason is None
    glm_c = next(c for c in result.candidates if c.catalog_id == "glm5")
    assert glm_c.status == "constant"
    assert glm_c.wrappers == [36, 36, 36, 36]
    qwen_c = next(c for c in result.candidates if c.catalog_id == "qwen2_5")
    assert qwen_c.status == "drifted"
    assert all(not s.dropped for s in result.samples)
    assert format_wrapper_line(result) == "wrapper=constant glm5 +36 spread=0"


def test_drift_across_lengths():
    local = {t: i + 1 for i, t in enumerate(TEXTS)}
    api = [local[t] + 10 + i * 8 for i, t in enumerate(TEXTS)]
    catalog = {"glm5": FakeVocab("glm5", local)}
    client = _client_for(TEXTS, api)

    result = run_wrapper(client, catalog, TEXTS)

    assert result.status == "drifted"
    assert result.catalog_id == "glm5"
    assert result.spread == 24
    assert result.candidates[0].status == "drifted"
    assert result.candidates[0].wrappers == [10, 18, 26, 34]
    assert format_wrapper_line(result) == "wrapper=drifted glm5 spread=24"


def test_missing_usage_and_http_400_dropped_all_bad_untrusted():
    local = {t: 2 for t in TEXTS}
    catalog = {"glm5": FakeVocab("glm5", local)}
    client = FakeClient(
        {
            TEXTS[0]: {"status_code": 200, "prompt_tokens": None},
            TEXTS[1]: {"status_code": 400, "prompt_tokens": 99},
            TEXTS[2]: {"status_code": 200, "prompt_tokens": None, "usage": None},
            TEXTS[3]: {"status_code": 400},
        }
    )

    result = run_wrapper(client, catalog, TEXTS)

    assert result.samples[0].dropped is True
    assert result.samples[0].drop_reason == "missing_prompt_tokens"
    assert result.samples[1].dropped is True
    assert result.samples[1].drop_reason == "http_non_2xx"
    assert result.samples[2].dropped is True
    assert result.samples[2].drop_reason == "missing_prompt_tokens"
    assert result.samples[3].dropped is True
    assert result.samples[3].drop_reason == "http_non_2xx"
    assert all(s.dropped for s in result.samples)
    assert result.status == "untrusted"
    assert result.catalog_id is None
    assert result.untrusted_reason == "too_few_valid_samples"
    assert result.candidates[0].status == "untrusted"
    assert format_wrapper_line(result) == "wrapper=untrusted"


def test_partial_drop_still_constant_if_two_valid():
    texts = ["aa", "bbbb", "cccccc"]
    glm = {"aa": 1, "bbbb": 2, "cccccc": 3}
    catalog = {"glm5": FakeVocab("glm5", glm)}
    client = FakeClient(
        {
            "aa": {"status_code": 200, "prompt_tokens": 37},
            "bbbb": {"status_code": 400, "prompt_tokens": 1},
            "cccccc": {"status_code": 200, "prompt_tokens": None},
        }
    )

    result = run_wrapper(client, catalog, texts)

    assert result.samples[1].dropped is True
    assert result.samples[1].drop_reason == "http_non_2xx"
    assert result.samples[2].dropped is True
    assert result.samples[2].drop_reason == "missing_prompt_tokens"
    # 只剩 1 条有效 → 整场 untrusted
    assert result.status == "untrusted"
    assert format_wrapper_line(result) == "wrapper=untrusted"

    client.responses["cccccc"] = {"status_code": 200, "prompt_tokens": 39}
    result2 = run_wrapper(client, catalog, texts)
    assert result2.samples[1].dropped is True
    assert result2.status == "constant"
    assert result2.value == 36
    assert result2.spread == 0


def test_fake_client_records_max_tokens_none_and_stream_off():
    local = {t: 1 for t in TEXTS}
    catalog = {"glm5": FakeVocab("glm5", local)}
    client = _client_for(TEXTS, [37] * len(TEXTS))

    run_wrapper(client, catalog, TEXTS)

    assert len(client.calls) == len(TEXTS)
    assert all(c["max_tokens"] is None for c in client.calls)
    assert all(c["stream"] is False for c in client.calls)
    assert all(c["temperature"] == 0 for c in client.calls)
    assert all(c["kind"] == "wrapper" for c in client.calls)
    assert all(c["messages"] == [{"role": "user", "content": c["text"]}] for c in client.calls)


def test_format_wrapper_line_shapes():
    local = {t: i + 1 for i, t in enumerate(TEXTS)}
    catalog = {"glm5": FakeVocab("glm5", local)}

    constant = run_wrapper(client=_client_for(TEXTS, [n + 36 for n in local.values()]), catalog=catalog, texts=TEXTS)
    assert format_wrapper_line(constant) == "wrapper=constant glm5 +36 spread=0"

    drifted = run_wrapper(
        client=_client_for(TEXTS, [local[t] + 2 + i * 3 for i, t in enumerate(TEXTS)]),
        catalog=catalog,
        texts=TEXTS,
    )
    assert format_wrapper_line(drifted) == f"wrapper=drifted glm5 spread={drifted.spread}"
    assert drifted.spread == 9

    bad = run_wrapper(
        client=FakeClient({t: {"status_code": 400} for t in TEXTS}),
        catalog=catalog,
        texts=TEXTS,
    )
    assert format_wrapper_line(bad) == "wrapper=untrusted"


def test_plus_minus_one_still_constant():
    local = {t: 2 for t in TEXTS}
    catalog = {"glm5": FakeVocab("glm5", local)}
    api = [38, 39, 38, 38]
    result = run_wrapper(_client_for(TEXTS, api), catalog, TEXTS)
    assert result.status == "constant"
    assert result.value == 36
    assert result.spread == 1
    assert format_wrapper_line(result) == "wrapper=constant glm5 +36 spread=1"


def test_two_constant_same_spread_different_value_is_drifted():
    glm = {t: 1 for t in TEXTS}
    qwen = {t: 5 for t in TEXTS}
    catalog = {
        "glm5": FakeVocab("glm5", glm),
        "qwen2_5": FakeVocab("qwen2_5", qwen),
    }
    # api - glm = 36；api - qwen = 32；两家都恒定，不猜哪家壳
    result = run_wrapper(_client_for(TEXTS, [37] * len(TEXTS)), catalog, TEXTS)
    assert {c.status for c in result.candidates} == {"constant"}
    assert result.candidates[0].value != result.candidates[1].value
    assert result.status == "drifted"
    assert result.catalog_id is None
    assert format_wrapper_line(result) == "wrapper=drifted"


def test_two_constant_same_spread_same_value_no_catalog():
    glm = {t: 1 for t in TEXTS}
    qwen = {t: 1 for t in TEXTS}
    catalog = {
        "glm5": FakeVocab("glm5", glm),
        "qwen2_5": FakeVocab("qwen2_5", qwen),
    }
    # 两家 encode 长度相同，API 减本地都是 +36；壳开销恒定，但不猜尺子
    result = run_wrapper(_client_for(TEXTS, [37] * len(TEXTS)), catalog, TEXTS)
    assert {c.status for c in result.candidates} == {"constant"}
    assert result.candidates[0].value == result.candidates[1].value == 36
    assert result.status == "constant"
    assert result.catalog_id is None
    assert result.value == 36
    assert result.spread == 0
    line = format_wrapper_line(result)
    assert line == "wrapper=constant +36 spread=0"
    assert "支持" not in line


def test_default_texts_and_completer_protocol():
    table = {t: len(t) for t in DEFAULT_WRAPPER_TEXTS}
    catalog = {"glm5": FakeVocab("glm5", table)}
    client = _client_for(list(DEFAULT_WRAPPER_TEXTS), [table[t] + 12 for t in DEFAULT_WRAPPER_TEXTS])
    assert isinstance(client, Completer)
    result = run_wrapper(client, catalog)
    assert [s.text for s in result.samples] == list(DEFAULT_WRAPPER_TEXTS)
    assert result.status == "constant"
    assert result.value == 12
