"""SKU 卡 / catalog A/B 离线单测：假 client，不打网。"""

from __future__ import annotations

import threading

from src.sku import (
    SKU_BASE,
    SKU_EMOJI,
    SKU_HI,
    SKU_SPECIAL,
    compare_sku_cards,
    format_sku_line,
    measure_sku_card,
    run_sku_ab,
)
from src.types import Completer, CompletionRecord


class FakeClient:
    def __init__(self, responses: dict[str, dict], *, effort: dict | None = None):
        self.responses = responses
        self.effort = effort or {}
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
        text = messages[0]["content"]
        with self._lock:
            self.calls.append(
                {
                    "text": text,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "extra": extra,
                    "kind": kind,
                    "stream": stream,
                }
            )
        if extra and extra.get("reasoning_effort") == "none":
            spec = dict(self.effort)
        else:
            spec = dict(self.responses.get(text, {}))
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
                "extra": extra,
            },
            status_code=spec.get("status_code", 200),
            latency_ms=0,
            prompt_tokens=prompt_tokens,
            completion_tokens=1,
            content=spec.get("content", ""),
            error=spec.get("error"),
            usage=usage,
        )


def _client(
    *,
    hi: int | None = 37,
    emoji_base: int = 20,
    emoji_delta: int | None = 16,
    special_delta: int | None = 3,
    hi_status: int = 200,
    emoji_base_status: int = 200,
    emoji_status: int = 200,
    special_status: int = 200,
    effort: str = "accepted",
) -> FakeClient:
    responses: dict[str, dict] = {
        SKU_HI: {"prompt_tokens": hi, "status_code": hi_status},
        SKU_BASE: {"prompt_tokens": emoji_base, "status_code": emoji_base_status},
        SKU_BASE + SKU_EMOJI: {
            "prompt_tokens": None if emoji_delta is None else emoji_base + emoji_delta,
            "status_code": emoji_status,
        },
        SKU_HI + SKU_SPECIAL: {
            "prompt_tokens": None
            if hi is None or special_delta is None
            else hi + special_delta,
            "status_code": special_status,
        },
    }
    if effort == "accepted":
        effort_spec: dict = {"status_code": 200, "prompt_tokens": hi or 1}
    elif effort == "zhipu_numeric":
        effort_spec = {
            "status_code": 400,
            "prompt_tokens": None,
            "content": "invalid parameter [1210]",
            "error": "HTTP 400: [1210]",
        }
    elif effort == "thinking_only":
        effort_spec = {
            "status_code": 400,
            "prompt_tokens": None,
            "content": "This is a thinking-only model; reasoning cannot be disabled.",
        }
    else:
        effort_spec = {
            "status_code": 422,
            "prompt_tokens": None,
            "error": "HTTP 422: bad request",
        }
    return FakeClient(responses, effort=effort_spec)


def test_fake_client_is_completer() -> None:
    assert isinstance(FakeClient({}), Completer)


def test_omen_style_shell_diff():
    clients = {
        "omen-alpha": _client(hi=37, effort="accepted"),
        "glm-5.3-flash": _client(hi=13, effort="zhipu_numeric"),
    }
    result = run_sku_ab(clients, target_id="omen-alpha")

    assert result.status == "shell_diff"
    assert result.target.hi_prompt_tokens == 37
    assert result.peers[0].peer_id == "glm-5.3-flash"
    assert result.peers[0].wrapper_offset == 24
    assert result.peers[0].effort_none_kind == "zhipu_numeric"
    assert result.peers[0].same_effort_kind is False
    assert result.target.effort_none.kind == "accepted"
    assert format_sku_line(result) == "sku=shell_diff hi=37 offset=+24 vs glm-5.3-flash"
    assert "支持" not in result.note
    assert "支持" not in result.peers[0].note


def test_same_shell_note_has_no_support():
    clients = {
        "a": _client(hi=37, effort="accepted"),
        "b": _client(hi=37, effort="accepted"),
    }
    result = run_sku_ab(clients, target_id="a")

    assert result.status == "same_shell"
    assert result.peers[0].wrapper_offset == 0
    assert result.peers[0].same_emoji is True
    assert result.peers[0].same_effort_kind is True
    assert result.note == "壳对齐，不能证明是同一条权重"
    assert "支持" not in result.note
    assert "支持" not in result.peers[0].note
    assert format_sku_line(result) == "sku=same_shell hi=37 offset=+0 vs b"


def test_adapter_diff_same_hi_different_effort():
    clients = {
        "a": _client(hi=37, effort="accepted"),
        "b": _client(hi=37, effort="zhipu_numeric"),
    }
    result = run_sku_ab(clients, target_id="a")

    assert result.status == "adapter_diff"
    assert result.peers[0].wrapper_offset == 0
    assert result.peers[0].same_effort_kind is False
    assert format_sku_line(result) == "sku=adapter_diff hi=37 offset=+0 vs b"


def test_max_tokens_is_none():
    client = _client(hi=37)
    measure_sku_card(client, model_id="x")

    assert len(client.calls) == 5
    assert all(c["max_tokens"] is None for c in client.calls)
    assert all(c["temperature"] == 0 for c in client.calls)
    assert all(c["stream"] is False for c in client.calls)
    kinds = [c["kind"] for c in client.calls]
    assert kinds == [
        "sku_hi",
        "sku_emoji_base",
        "sku_emoji",
        "sku_special",
        "sku_effort_none",
    ]
    assert client.calls[-1]["extra"] == {"reasoning_effort": "none"}
    assert all(c["extra"] is None for c in client.calls[:-1])


def test_format_sku_line_insufficient():
    target = measure_sku_card(
        _client(hi=None, hi_status=200),
        model_id="gone",
    )
    peer = measure_sku_card(_client(hi=13), model_id="peer")
    result = compare_sku_cards(target, [peer])

    assert target.hi_prompt_tokens is None
    assert result.status == "insufficient"
    assert format_sku_line(result) == "sku=insufficient"


def test_emoji_and_special_use_api_delta():
    client = _client(hi=37, emoji_base=20, emoji_delta=16, special_delta=3)
    card = measure_sku_card(client, model_id="x")

    assert card.emoji_delta == 16
    assert card.special_image_delta == 3
    emoji_sig = next(s for s in card.signals if s.name == "emoji")
    special_sig = next(s for s in card.signals if s.name == "special")
    assert emoji_sig.delta == 16
    assert special_sig.delta == 3
    assert client.calls[1]["text"] == SKU_BASE
    assert client.calls[2]["text"] == SKU_BASE + SKU_EMOJI
    assert client.calls[3]["text"] == SKU_HI + SKU_SPECIAL


def test_emoji_side_fail_delta_none():
    client = _client(hi=37, emoji_status=500, emoji_delta=None)
    card = measure_sku_card(client, model_id="x")
    assert card.emoji_delta is None
    emoji_sig = next(s for s in card.signals if s.name == "emoji")
    assert emoji_sig.kind == "http_error"


def test_adapter_diff_special_delta():
    clients = {
        "a": _client(hi=37, special_delta=1, effort="accepted"),
        "b": _client(hi=37, special_delta=8, effort="accepted"),
    }
    result = run_sku_ab(clients, target_id="a")
    assert result.status == "adapter_diff"
    assert result.peers[0].wrapper_offset == 0
    assert result.peers[0].same_effort_kind is True


def test_special_one_side_missing_not_adapter():
    clients = {
        "a": _client(hi=37, special_delta=1, effort="accepted"),
        "b": _client(hi=37, special_delta=None, special_status=500, effort="accepted"),
    }
    result = run_sku_ab(clients, target_id="a")
    assert result.status == "same_shell"
    assert result.peers[0].special_image_delta_peer is None


def test_insufficient_no_peers():
    target = measure_sku_card(_client(hi=37), model_id="solo")
    result = compare_sku_cards(target, [])
    assert result.status == "insufficient"
    assert format_sku_line(result) == "sku=insufficient"


def test_thinking_only_effort():
    card = measure_sku_card(_client(hi=37, effort="thinking_only"), model_id="t")
    assert card.effort_none.kind == "thinking_only"
    assert card.effort_none.http == 400


def test_shell_diff_beats_adapter():
    clients = {
        "target": _client(hi=37, effort="accepted"),
        "thick": _client(hi=13, effort="accepted"),
        "same_hi": _client(hi=37, effort="zhipu_numeric"),
    }
    result = run_sku_ab(clients, target_id="target")
    assert result.status == "shell_diff"
    assert format_sku_line(result) == "sku=shell_diff hi=37 offset=+24 vs thick"


def test_run_sku_ab_measures_target_first():
    order: list[str] = []

    class OrderClient(FakeClient):
        def __init__(self, mid: str, hi: int):
            super().__init__(
                _client(hi=hi).responses,
                effort=_client(hi=hi).effort,
            )
            self.mid = mid

        def complete(self, *args, **kwargs):
            if not order or order[-1] != self.mid:
                order.append(self.mid)
            return super().complete(*args, **kwargs)

    clients = {
        "peer": OrderClient("peer", 13),
        "target": OrderClient("target", 37),
    }
    result = run_sku_ab(clients, target_id="target")
    assert order == ["target", "peer"]
    assert result.cards[0].model_id == "target"
    assert [c.model_id for c in result.cards[1:]] == ["peer"]
