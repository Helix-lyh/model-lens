"""L4 错误信封离线单测：按 extra / role 分支的 FakeClient，不打网。"""

from __future__ import annotations

from src.envelopes import format_envelopes_line, run_envelopes
from src.types import Completer, CompletionRecord


class FakeClient:
    """按 extra、role、kind 分支返回。不假设 extra 一定被网关吃掉。"""

    def __init__(
        self,
        *,
        by_extra: dict[str, dict] | None = None,
        by_role: dict[str, dict] | None = None,
        by_kind: dict[str, dict] | None = None,
        default: dict | None = None,
    ):
        self.by_extra = by_extra or {}
        self.by_role = by_role or {}
        self.by_kind = by_kind or {}
        self.default = default if default is not None else {"status_code": 200, "content": "ok"}
        self.calls: list[dict] = []

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
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "extra": extra,
                "kind": kind,
                "stream": stream,
            }
        )
        spec = self._pick(messages, extra, kind)
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
            status_code=spec.get("status_code"),
            latency_ms=0,
            prompt_tokens=spec.get("prompt_tokens"),
            completion_tokens=spec.get("completion_tokens"),
            content=spec.get("content"),
            raw=spec.get("raw"),
            error=spec.get("error"),
            usage=spec.get("usage"),
        )

    def _pick(self, messages: list[dict], extra: dict | None, kind: str) -> dict:
        extra = extra or {}
        if extra.get("temperature") == "hot" and "temperature" in self.by_extra:
            return self.by_extra["temperature"]
        if extra.get("reasoning_effort") == "none" and "reasoning_effort" in self.by_extra:
            return self.by_extra["reasoning_effort"]
        if messages:
            role = messages[0].get("role")
            if role in self.by_role:
                return self.by_role[role]
        if kind in self.by_kind:
            return self.by_kind[kind]
        return self.default


def _by_name(result) -> dict[str, object]:
    return {p.name: p for p in result.probes}


_GO_UNMARSHAL = (
    "json: cannot unmarshal string into Go struct field ***.temperature of type float64"
)


def test_go_unmarshal_is_go():
    client = FakeClient(
        by_extra={
            "temperature": {
                "status_code": 500,
                "error": _GO_UNMARSHAL,
            }
        }
    )

    result = run_envelopes(client)

    assert result.status == "ok"
    assert result.family == "go"
    probes = _by_name(result)
    assert probes["temperature_wrong_type"].kind == "go_json"
    assert probes["temperature_wrong_type"].http == 500
    assert probes["temperature_wrong_type"].detail is not None
    assert "cannot unmarshal" in probes["temperature_wrong_type"].detail
    line = format_envelopes_line(result)
    assert "envelopes=go" in line
    assert "支持" not in line


def test_go_and_serde_is_mixed():
    client = FakeClient(
        by_extra={
            "temperature": {
                "status_code": 500,
                "error": _GO_UNMARSHAL,
            }
        },
        by_kind={
            "env_bad_role": {
                "status_code": 400,
                "error": 'invalid type: string "wizard", expected f32',
            }
        },
    )

    result = run_envelopes(client)

    assert result.status == "ok"
    assert result.family == "mixed"
    assert result.note == "同一入口两套信封"
    probes = _by_name(result)
    assert probes["temperature_wrong_type"].kind == "go_json"
    assert probes["bad_role"].kind == "serde"
    line = format_envelopes_line(result)
    assert line == "envelopes=mixed go+rust_serde"
    assert "支持" not in line


def test_serde_text_is_rust_serde():
    client = FakeClient(
        by_extra={
            "temperature": {
                "status_code": 400,
                "error": 'invalid type: string "hot", expected f32',
            }
        }
    )

    result = run_envelopes(client)

    assert result.status == "ok"
    assert result.family == "rust_serde"
    probes = _by_name(result)
    assert probes["temperature_wrong_type"].kind == "serde"
    assert probes["temperature_wrong_type"].http == 400
    assert probes["temperature_wrong_type"].detail is not None
    assert "expected f32" in probes["temperature_wrong_type"].detail
    assert probes["developer_role"].kind == "accepted"
    line = format_envelopes_line(result)
    assert line == "envelopes=rust_serde temperature_hot=serde developer=accepted"
    assert "支持" not in line
    hot_call = next(c for c in client.calls if c["kind"] == "env_temperature_type")
    assert hot_call["extra"] == {"temperature": "hot"}


def test_openai_and_anthropic_is_mixed():
    client = FakeClient(
        by_kind={
            "env_temperature_type": {
                "status_code": 400,
                "error": '{"error":{"type":"invalid_request_error","message":"bad temp"}}',
            },
            "env_effort_none": {
                "status_code": 400,
                "raw": {"type": "error", "error": {"type": "invalid_request_error", "message": "bad"}},
            },
        }
    )

    result = run_envelopes(client)

    assert result.status == "ok"
    assert result.family == "mixed"
    assert result.note == "同一入口两套信封"
    probes = _by_name(result)
    assert probes["temperature_wrong_type"].kind == "openai_invalid"
    assert probes["reasoning_effort_none"].kind == "anthropic_error"
    line = format_envelopes_line(result)
    assert line == "envelopes=mixed openai+anthropic"
    assert "支持" not in line


def test_developer_accepted_wizard_rejected():
    client = FakeClient(
        by_role={
            "wizard": {"status_code": 400, "error": "unknown role: wizard"},
            "developer": {"status_code": 200, "content": "hi", "prompt_tokens": 4},
        }
    )

    result = run_envelopes(client)

    probes = _by_name(result)
    assert probes["bad_role"].http == 400
    assert probes["bad_role"].kind == "role_rejected"
    assert probes["developer_role"].http == 200
    assert probes["developer_role"].kind == "accepted"
    assert probes["developer_role"].prompt_tokens == 4
    wizard_call = next(c for c in client.calls if c["kind"] == "env_bad_role")
    assert wizard_call["messages"][0]["role"] == "wizard"
    developer_call = next(c for c in client.calls if c["kind"] == "env_developer")
    assert developer_call["messages"][0]["role"] == "developer"


def test_max_tokens_is_none():
    client = FakeClient()
    run_envelopes(client)

    assert client.calls
    assert all(c["max_tokens"] is None for c in client.calls)
    assert all(c["stream"] is False for c in client.calls)
    range_call = client.calls[0]
    assert range_call["kind"] == "env_temperature_range"
    assert range_call["temperature"] == 2.0
    assert range_call["extra"] is None
    assert [c["kind"] for c in client.calls] == [
        "env_temperature_range",
        "env_temperature_type",
        "env_effort_none",
        "env_bad_role",
        "env_developer",
    ]


def test_format_line_has_no_zhichi():
    serde = run_envelopes(
        FakeClient(
            by_extra={
                "temperature": {
                    "status_code": 400,
                    "error": "failed to deserialize untagged enum Variant",
                }
            }
        )
    )
    mixed = run_envelopes(
        FakeClient(
            by_kind={
                "env_temperature_type": {
                    "status_code": 400,
                    "error": "invalid_request_error",
                },
                "env_effort_none": {
                    "status_code": 400,
                    "error": '{"type":"error","error":{"message":"x"},"modelerror":true}',
                },
            }
        )
    )
    empty = run_envelopes(FakeClient(default={}))
    lines = [
        format_envelopes_line(serde),
        format_envelopes_line(mixed),
        format_envelopes_line(empty),
    ]
    assert empty.status == "insufficient"
    assert empty.family is None
    assert lines[2] == "envelopes=insufficient"
    for line in lines:
        assert "支持" not in line


def test_fake_client_is_completer() -> None:
    assert isinstance(FakeClient(), Completer)
