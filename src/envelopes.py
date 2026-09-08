"""畸形参数的错误信封指纹。认服务栈，不认权重。

把越界温度、错类型、无效 role 等请求的 HTTP / 报错原文收成附录：
数字码、serde、OpenAI / Anthropic 信封、接不接受 developer。
不进家族栏，不合成总分。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from src.types import Completer, CompletionRecord
from src.usage import http_ok, record_prompt_tokens

EnvelopeStatus = Literal["ok", "insufficient"]

_HI = [{"role": "user", "content": "hi"}]
_DETAIL_LIMIT = 240
_MIN_VALID = 2

_ANTHROPIC_TYPE = re.compile(r'"type"\s*:\s*"error"')
_ANTHROPIC_STRUCT = re.compile(r'\{\s*"type"\s*:\s*"error"\s*,\s*"error"\s*:')
_SECRET_CHUNK = re.compile(
    r"(?i)(?:(?:api[_-]?key|authorization|password|secret|access_token|auth_token)"
    r"\s*[:=]\s*)\S+|Bearer\s+\S+|sk-[A-Za-z0-9_-]+"
)

_STACK_ORDER = ("go", "rust_serde", "zhipu", "openai", "anthropic")
_KIND_TO_STACK = {
    "go_json": "go",
    "serde": "rust_serde",
    "zhipu_numeric": "zhipu",
    "openai_invalid": "openai",
    "anthropic_error": "anthropic",
}


@dataclass
class EnvelopeProbe:
    name: str
    http: int | None
    kind: str
    detail: str | None
    prompt_tokens: int | None


@dataclass
class EnvelopeResult:
    status: EnvelopeStatus
    family: str | None
    probes: list[EnvelopeProbe]
    note: str


def run_envelopes(client: Completer) -> EnvelopeResult:
    """按固定顺序打五条畸形请求，从报错原文认服务栈。"""
    probes = [_run_probe(client, spec) for spec in _PROBE_SPECS]
    valid = [p for p in probes if _valid(p)]
    if len(valid) < _MIN_VALID:
        return EnvelopeResult(
            status="insufficient",
            family=None,
            probes=probes,
            note="有效探针不足",
        )
    family, note = _family_of(valid)
    return EnvelopeResult(status="ok", family=family, probes=probes, note=note)


def format_envelopes_line(result: EnvelopeResult) -> str:
    """CLI 一行。例：envelopes=rust_serde temperature_hot=serde developer=accepted"""
    if result.status == "insufficient":
        return "envelopes=insufficient"
    if result.family == "mixed":
        stacks = _mixed_stacks(result.probes)
        if stacks:
            return f"envelopes=mixed {'+'.join(stacks)}"
        return "envelopes=mixed"
    parts = [f"envelopes={result.family}"]
    by_name = {p.name: p for p in result.probes}
    hot = by_name.get("temperature_wrong_type")
    if hot is not None:
        parts.append(f"temperature_hot={hot.kind}")
    developer = by_name.get("developer_role")
    if developer is not None:
        parts.append(f"developer={developer.kind}")
    return " ".join(parts)


def _classify(rec: CompletionRecord) -> tuple[str, str | None]:
    """从 status / error / content / raw 判信封种类，detail 截断 240。"""
    blob = _text_from_record(rec)
    detail = _clip_detail(blob)
    if http_ok(rec):
        return "accepted", detail

    if "[1210]" in blob or "[1214]" in blob:
        return "zhipu_numeric", detail

    low = blob.lower()
    if "cannot unmarshal" in low and ("go struct" in low or "go value" in low):
        return "go_json", detail

    if (
        "untagged enum" in low
        or "deserialize" in low
        or "expected f32" in low
    ):
        return "serde", detail

    if _ANTHROPIC_TYPE.search(low) and (
        "modelerror" in low or _ANTHROPIC_STRUCT.search(low)
    ):
        return "anthropic_error", detail

    if "invalid_request_error" in blob:
        return "openai_invalid", detail

    if rec.kind == "env_bad_role":
        return "role_rejected", detail

    if rec.status_code is not None or blob:
        return "other", detail
    return "", None


def _run_probe(client: Completer, spec: dict[str, Any]) -> EnvelopeProbe:
    extra = spec["extra"]
    rec = client.complete(
        spec["messages"],
        temperature=spec["temperature"],
        max_tokens=None,
        extra=dict(extra) if extra is not None else None,
        kind=spec["kind"],
        stream=False,
    )
    kind, detail = _classify(rec)
    return EnvelopeProbe(
        name=spec["name"],
        http=rec.status_code,
        kind=kind,
        detail=detail,
        prompt_tokens=_prompt_tokens(rec),
    )


def _family_of(valid: list[EnvelopeProbe]) -> tuple[str, str]:
    kinds = {p.kind for p in valid}
    has_go = "go_json" in kinds
    has_serde = "serde" in kinds
    has_zhipu = "zhipu_numeric" in kinds
    has_openai = "openai_invalid" in kinds
    has_anthropic = "anthropic_error" in kinds
    others = has_serde or has_zhipu or has_openai or has_anthropic

    if has_go and others:
        return "mixed", "同一入口两套信封"
    if has_anthropic and (has_serde or has_openai):
        return "mixed", "同一入口两套信封"
    if has_go:
        return "go", ""
    if has_serde:
        return "rust_serde", ""
    if has_zhipu:
        return "zhipu", ""
    if has_anthropic:
        return "anthropic", ""
    if has_openai:
        return "openai", ""
    return "unknown", ""


def _mixed_stacks(probes: list[EnvelopeProbe]) -> list[str]:
    seen: set[str] = set()
    for p in probes:
        stack = _KIND_TO_STACK.get(p.kind)
        if stack:
            seen.add(stack)
    return [name for name in _STACK_ORDER if name in seen]


def _valid(probe: EnvelopeProbe) -> bool:
    return probe.http is not None or bool(probe.kind)


def _prompt_tokens(rec: CompletionRecord) -> int | None:
    return record_prompt_tokens(rec)


def _text_from_record(rec: CompletionRecord) -> str:
    chunks: list[str] = []
    if rec.error:
        chunks.append(str(rec.error))
    if rec.content:
        chunks.append(str(rec.content))
    raw = rec.raw
    if raw is not None:
        if isinstance(raw, str):
            chunks.append(raw)
        else:
            try:
                chunks.append(json.dumps(raw, ensure_ascii=False))
            except TypeError:
                chunks.append(str(raw))
    return "\n".join(chunks)


def _clip_detail(text: str) -> str | None:
    cleaned = _SECRET_CHUNK.sub("[redacted]", text).strip()
    if not cleaned:
        return None
    if len(cleaned) > _DETAIL_LIMIT:
        return cleaned[:_DETAIL_LIMIT]
    return cleaned


_PROBE_SPECS: list[dict[str, Any]] = [
    {
        "name": "temperature_out_of_range",
        "messages": list(_HI),
        "temperature": 2.0,
        "extra": None,
        "kind": "env_temperature_range",
    },
    {
        "name": "temperature_wrong_type",
        "messages": list(_HI),
        "temperature": 0,
        "extra": {"temperature": "hot"},
        "kind": "env_temperature_type",
    },
    {
        "name": "reasoning_effort_none",
        "messages": list(_HI),
        "temperature": 0,
        "extra": {"reasoning_effort": "none"},
        "kind": "env_effort_none",
    },
    {
        "name": "bad_role",
        "messages": [{"role": "wizard", "content": "hi"}],
        "temperature": 0,
        "extra": None,
        "kind": "env_bad_role",
    },
    {
        "name": "developer_role",
        "messages": [{"role": "developer", "content": "say hi"}],
        "temperature": 0,
        "extra": None,
        "kind": "env_developer",
    },
]
