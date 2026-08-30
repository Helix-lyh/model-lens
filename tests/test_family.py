"""Module F 离线单测：假 client / 假 vocab，不打网、不下载词表。"""

from __future__ import annotations

import threading

import pytest

from src.family import format_family_line, run_family
from src.probes import load_family_probes
from src.types import Completer, CompletionRecord, Probe

BASE, _ = load_family_probes()


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
        del extra, stream
        text = messages[0]["content"]
        with self._lock:
            self.calls.append(
                {
                    "text": text,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "kind": kind,
                }
            )
        spec = self.responses.get(text, {})
        prompt_tokens = spec.get("prompt_tokens")
        if "usage" in spec:
            usage = spec["usage"]
        elif type(prompt_tokens) is int:
            usage = {"prompt_tokens": prompt_tokens}
            if "cached_tokens" in spec:
                usage["cached_tokens"] = spec["cached_tokens"]
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
            },
            status_code=spec.get("status_code", 200),
            latency_ms=0,
            prompt_tokens=prompt_tokens,
            completion_tokens=1,
            content="",
            usage=usage,
        )


def _probes(n: int) -> list[Probe]:
    return [Probe(id=f"p{i:02d}", text=f"PROBE{i:02d}_" + "x" * (i + 3)) for i in range(n)]


def _table(base: str, probes: list[Probe], n_hats: list[int], *, base_len: int = 4, x_len: int = 99) -> dict[str, int]:
    table = {base: base_len}
    for probe, n in zip(probes, n_hats, strict=True):
        table[base + probe.text] = base_len + n
        table[probe.text] = x_len
    return table


def _client_for(base: str, probes: list[Probe], deltas: list[int], *, overhead: int = 50) -> FakeClient:
    responses: dict[str, dict] = {base: {"prompt_tokens": overhead, "status_code": 200}}
    for probe, delta in zip(probes, deltas, strict=True):
        responses[base + probe.text] = {
            "prompt_tokens": overhead + delta,
            "status_code": 200,
        }
    return FakeClient(responses)


def test_perfect_glm5_high_confidence():
    probes = _probes(14)
    glm_hats = [i + 2 for i in range(14)]
    qwen_hats = [i + 2 if i < 6 else i + 10 for i in range(14)]
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, glm_hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, qwen_hats)),
    }
    client = _client_for(BASE, probes, glm_hats)

    result = run_family(client, catalog, BASE, probes, claimed_model="ignored")

    assert result.status == "ok"
    assert result.family == "glm5"
    assert result.confidence == "high"
    assert result.hits == 14
    assert result.n_probes == 14
    assert result.l1 == 0
    assert result.runner_up == "qwen2_5"
    assert result.runner_up_hits == 6
    assert result.runner_up_l1 == 64
    line = format_family_line(result)
    assert "family=glm5" in line
    assert "hits=14/14" in line
    assert "confidence=high" in line
    assert "runner_up=qwen2_5" in line
    kinds = [c["kind"] for c in client.calls]
    assert kinds[0] == "family_base"
    assert kinds.count("family_base") == 1
    assert all(c["temperature"] == 0 and c["max_tokens"] is None for c in client.calls)


def test_l1_margin_lt_3_ambiguous():
    probes = _probes(8)
    glm_hats = [2] * 8
    qwen_hats = [2, 2, 2, 2, 2, 2, 3, 3]
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, glm_hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, qwen_hats)),
    }
    client = _client_for(BASE, probes, glm_hats)

    result = run_family(client, catalog, BASE, probes)

    assert result.status == "ambiguous"
    assert result.family == "ambiguous"
    assert result.confidence is None
    assert result.l1 == 0
    assert result.runner_up_l1 == 2
    assert (result.runner_up_l1 or 0) - (result.l1 or 0) < 3


def test_best_exact_hits_lt_6_ambiguous():
    probes = _probes(8)
    api = [2, 2, 2, 2, 2, 3, 3, 3]
    glm_hats = [2, 2, 2, 2, 2, 2, 2, 2]
    qwen_hats = [12] * 8
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, glm_hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, qwen_hats)),
    }
    client = _client_for(BASE, probes, api)

    result = run_family(client, catalog, BASE, probes)

    assert result.hits == 5
    assert result.l1 == 3
    assert result.l1 is not None and result.l1 < 2 * result.n_probes
    assert result.status == "ambiguous"
    assert result.family == "ambiguous"


def test_best_l1_ge_2n_ambiguous():
    probes = _probes(8)
    api = [2, 2, 2, 2, 2, 2, 10, 10]
    glm_hats = [2] * 8
    qwen_hats = [22] * 8
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, glm_hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, qwen_hats)),
    }
    client = _client_for(BASE, probes, api)

    result = run_family(client, catalog, BASE, probes)

    assert result.hits == 6
    assert result.l1 == 16
    assert result.l1 is not None and result.l1 >= 2 * result.n_probes
    assert result.status == "ambiguous"
    assert result.family == "ambiguous"


def test_base_missing_prompt_tokens_untrusted():
    probes = _probes(8)
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, [2] * 8)),
    }
    client = FakeClient({BASE: {"status_code": 200, "prompt_tokens": None}})

    result = run_family(client, catalog, BASE, probes)

    assert result.status == "token_untrusted"
    assert result.family == "token_untrusted"
    assert result.confidence is None
    assert result.untrusted_reason == "base_missing_prompt_tokens"
    assert format_family_line(result) == "family=token_untrusted"
    assert all(c["kind"] != "family_probe:p00" for c in client.calls)


def test_single_probe_http_500_dropped_rest_ok():
    probes = _probes(14)
    glm_hats = [i + 2 for i in range(14)]
    qwen_hats = [i + 20 for i in range(14)]
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, glm_hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, qwen_hats)),
    }
    client = _client_for(BASE, probes, glm_hats)
    client.responses[BASE + probes[0].text] = {"status_code": 500, "prompt_tokens": None}

    result = run_family(client, catalog, BASE, probes)

    assert result.probes[0].dropped is True
    assert result.probes[0].drop_reason == "http_non_2xx"
    assert result.n_probes == 13
    assert result.status == "ok"
    assert result.family == "glm5"
    assert result.hits == 13
    assert result.confidence == "high"


def test_fewer_than_8_valid_untrusted():
    probes = _probes(7)
    hats = [2] * 7
    catalog = {"glm5": FakeVocab("glm5", _table(BASE, probes, hats))}
    client = _client_for(BASE, probes, hats)

    result = run_family(client, catalog, BASE, probes)

    assert result.status == "token_untrusted"
    assert result.family == "token_untrusted"
    assert result.n_probes == 7
    assert result.untrusted_reason == "too_few_valid_probes"


def test_delta_api_lt_1_dropped_may_untrusted():
    probes = _probes(8)
    hats = [2] * 8
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, [9] * 8)),
    }
    client = _client_for(BASE, probes, hats)
    client.responses[BASE + probes[-1].text] = {"status_code": 200, "prompt_tokens": 50}

    result = run_family(client, catalog, BASE, probes)

    assert result.probes[-1].dropped is True
    assert result.probes[-1].drop_reason == "delta_out_of_range"
    assert result.probes[-1].delta_api == 0
    assert result.n_probes == 7
    assert result.status == "token_untrusted"
    assert result.family == "token_untrusted"


def test_fake_client_is_completer() -> None:
    assert isinstance(FakeClient({}), Completer)


def test_complete_exception_propagates() -> None:
    class Boom(Exception):
        pass

    class RaisingClient:
        def complete(
            self,
            messages: list[dict],
            *,
            temperature: float = 0.0,
            max_tokens: int | None = None,
            extra: dict | None = None,
            kind: str = "chat",
            stream: bool = False,
        ):
            del messages, temperature, max_tokens, extra, kind, stream
            raise Boom("network")

    probes = _probes(8)
    catalog = {"glm5": FakeVocab("glm5", _table(BASE, probes, [2] * 8))}
    with pytest.raises(Boom):
        run_family(RaisingClient(), catalog, BASE, probes)


def test_n_hat_uses_differential_not_encode_x():
    probes = _probes(8)
    diff_hats = [3] * 8
    encode_x = 99
    table = _table(BASE, probes, diff_hats, x_len=encode_x)
    vocab = FakeVocab("weird", table)
    assert vocab.encode_len(probes[0].text) == encode_x
    assert vocab.n_hat(BASE, probes[0].text) == 3
    assert vocab.encode_len(probes[0].text) != vocab.n_hat(BASE, probes[0].text)

    catalog = {
        "weird": vocab,
        "other": FakeVocab("other", _table(BASE, probes, [20] * 8, x_len=encode_x)),
    }
    client = _client_for(BASE, probes, diff_hats)

    result = run_family(client, catalog, BASE, probes)

    for pd in result.probes:
        assert pd.n_hat["weird"] == 3
        assert pd.n_hat["weird"] != encode_x
        assert pd.delta_api == 3
    assert result.family == "weird"
    assert result.hits == 8


def test_usage_prompt_tokens_preferred_over_top_level():
    probes = _probes(8)
    hats = [2] * 8
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, [9] * 8)),
    }
    client = _client_for(BASE, probes, hats, overhead=50)
    client.responses[BASE] = {
        "status_code": 200,
        "prompt_tokens": 999,
        "usage": {"prompt_tokens": 50},
    }
    client.responses[BASE + probes[0].text] = {
        "status_code": 200,
        "prompt_tokens": 1,
        "usage": {"prompt_tokens": 52},
    }

    result = run_family(client, catalog, BASE, probes)

    assert result.status == "ok"
    assert result.family == "glm5"
    assert result.probes[0].prompt_tokens_base == 50
    assert result.probes[0].prompt_tokens_probe == 52
    assert result.probes[0].delta_api == 2
    assert result.probes[0].dropped is False
    assert result.hits == 8


def test_base_cached_gt_prompt_untrusted():
    probes = _probes(8)
    catalog = {"glm5": FakeVocab("glm5", _table(BASE, probes, [2] * 8))}
    client = FakeClient(
        {
            BASE: {
                "status_code": 200,
                "prompt_tokens": 50,
                "usage": {"prompt_tokens": 50, "cached_tokens": 80},
            }
        }
    )

    result = run_family(client, catalog, BASE, probes)

    assert result.status == "token_untrusted"
    assert result.family == "token_untrusted"
    assert result.untrusted_reason == "base_cached_gt_prompt"
    assert all(c["kind"] != "family_probe:p00" for c in client.calls)


def test_probe_cached_gt_prompt_dropped():
    probes = _probes(14)
    glm_hats = [i + 2 for i in range(14)]
    qwen_hats = [i + 20 for i in range(14)]
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, glm_hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, qwen_hats)),
    }
    client = _client_for(BASE, probes, glm_hats, overhead=50)
    client.responses[BASE + probes[0].text] = {
        "status_code": 200,
        "prompt_tokens": 52,
        "usage": {"prompt_tokens": 52, "cached_tokens": 90},
    }

    result = run_family(client, catalog, BASE, probes)

    assert result.probes[0].dropped is True
    assert result.probes[0].drop_reason == "cached_gt_prompt"
    assert result.n_probes == 13
    assert result.status == "ok"
    assert result.family == "glm5"


def test_base_cached_positive_probe_cached_zero_dropped():
    probes = _probes(14)
    glm_hats = [i + 2 for i in range(14)]
    qwen_hats = [i + 20 for i in range(14)]
    catalog = {
        "glm5": FakeVocab("glm5", _table(BASE, probes, glm_hats)),
        "qwen2_5": FakeVocab("qwen2_5", _table(BASE, probes, qwen_hats)),
    }
    client = _client_for(BASE, probes, glm_hats, overhead=50)
    client.responses[BASE]["cached_tokens"] = 10
    for probe, hat in zip(probes, glm_hats, strict=True):
        client.responses[BASE + probe.text]["cached_tokens"] = 10
    client.responses[BASE + probes[0].text]["cached_tokens"] = 0

    result = run_family(client, catalog, BASE, probes)

    assert result.probes[0].dropped is True
    assert result.probes[0].drop_reason == "cache_inconsistent"
    assert all(not d.dropped for d in result.probes[1:])
    assert result.n_probes == 13
    assert result.status == "ok"
    assert result.family == "glm5"
