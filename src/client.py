"""多渠道客户端 + jsonl 记录。密钥不落盘，usage 不做本地估算。

默认非流式。stream=True 只给题库测 TTFT / decode TPS；家族栏禁止开。
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from src.channels.base import apply_auth
from src.channels.openai_completions import chat_completions_url
from src.channels.resolve import get_adapter, resolve_channel
from src.config import resolve_api_key
from src.limits import official_max_output
from src.stream import (
    StreamUnsupported,
    apply_stream,
    assemble_stream,
    content_delta,
    feed_sse,
    flush_sse,
)
from src.reasoning import extract_reasoning
from src.types import CompletionRecord, Endpoint
from src.usage import (
    TokenUsage,
    count_request_chars,
    count_text_chars,
    derive_metrics,
    metrics_asdict,
    usage_asdict,
)


def _http_error_message(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
    except ValueError:
        return f"HTTP {resp.status_code}"
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            if isinstance(msg, str) and msg:
                return f"HTTP {resp.status_code}: {msg}"
        if isinstance(err, str) and err:
            return f"HTTP {resp.status_code}: {err}"
        msg = payload.get("message")
        if isinstance(msg, str) and msg:
            return f"HTTP {resp.status_code}: {msg}"
    return f"HTTP {resp.status_code}"


class JsonlRecorder:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: CompletionRecord) -> None:
        line = json.dumps(asdict(record), ensure_ascii=False, default=str)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


class ChatClient:
    def __init__(
        self,
        endpoint: Endpoint,
        recorder: JsonlRecorder,
        *,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        http_client: httpx.Client | None = None,
    ):
        self.endpoint = endpoint
        self.resolved = resolve_channel(endpoint)
        self.adapter = get_adapter(self.resolved.api)
        self.recorder = recorder
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._api_key = resolve_api_key(endpoint)
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout_s)

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
        if max_tokens is None:
            max_tokens = official_max_output(self.resolved.model)
        prepared = self.adapter.prepare(
            self.resolved,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
        )
        stream_note: str | None = None
        use_stream = stream
        if stream:
            try:
                prepared = apply_stream(
                    prepared, self.resolved.api, compat=self.resolved.compat
                )
            except StreamUnsupported as exc:
                use_stream = False
                stream_note = str(exc)
        headers = apply_auth(
            prepared.headers,
            auth=self.resolved.auth,
            api_key=self._api_key,
        )
        attempts = self.max_retries + 1
        record: CompletionRecord | None = None

        for attempt in range(attempts):
            t0 = time.perf_counter()
            try:
                if use_stream:
                    record = self._stream_once(
                        kind=kind,
                        prepared=prepared,
                        headers=headers,
                        t0=t0,
                    )
                else:
                    resp = self._http.request(
                        prepared.method,
                        prepared.url,
                        json=prepared.body,
                        headers=headers,
                    )
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    status = resp.status_code
                    if 500 <= status <= 599 and attempt < attempts - 1:
                        continue
                    if 200 <= status < 300:
                        record = self._success(
                            kind=kind,
                            request=prepared.body,
                            resp=resp,
                            latency_ms=latency_ms,
                        )
                        break
                    record = self._failure(
                        kind=kind,
                        request=prepared.body,
                        status_code=status,
                        latency_ms=latency_ms,
                        error=_http_error_message(resp),
                    )
                    break
            except httpx.RequestError as exc:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if attempt < attempts - 1:
                    continue
                record = self._failure(
                    kind=kind,
                    request=prepared.body,
                    status_code=None,
                    latency_ms=latency_ms,
                    error=str(exc) or type(exc).__name__,
                )
                break

            if record is None:
                continue
            if (
                use_stream
                and record.status_code is not None
                and 500 <= record.status_code <= 599
                and attempt < attempts - 1
            ):
                continue
            break

        assert record is not None
        if stream:
            record = self._annotate_stream_metrics(
                record, requested=True, used=use_stream, note=stream_note
            )
        self.recorder.write(record)
        return record

    def _success(
        self,
        *,
        kind: str,
        request: dict[str, Any],
        resp: httpx.Response,
        latency_ms: int,
    ) -> CompletionRecord:
        error: str | None = None
        raw: dict[str, Any] | None = None
        content: str | None = None
        usage = TokenUsage()
        try:
            data = resp.json()
        except ValueError:
            error = f"HTTP {resp.status_code}: 响应不是 JSON"
            data = None
        reasoning: str | None = None
        if data is not None:
            raw = self.adapter.slim_raw(data)
            content = self.adapter.parse_content(data)
            reasoning = extract_reasoning(data)
            usage = self.adapter.parse_token_usage(data)
        metrics = derive_metrics(
            usage,
            latency_ms=latency_ms,
            input_chars=count_request_chars(request),
            output_chars=count_text_chars(content),
        )
        return CompletionRecord(
            kind=kind,
            endpoint=self.resolved.base_url,
            model=self.resolved.model,
            request=request,
            status_code=resp.status_code,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            content=content,
            reasoning=reasoning,
            raw=raw,
            error=error,
            channel=self.resolved.channel_id,
            api=self.resolved.api,
            usage=usage_asdict(usage),
            metrics=metrics_asdict(metrics),
        )

    def _failure(
        self,
        *,
        kind: str,
        request: dict[str, Any],
        status_code: int | None,
        latency_ms: int,
        error: str,
    ) -> CompletionRecord:
        return CompletionRecord(
            kind=kind,
            endpoint=self.resolved.base_url,
            model=self.resolved.model,
            request=request,
            status_code=status_code,
            latency_ms=latency_ms,
            prompt_tokens=None,
            completion_tokens=None,
            content=None,
            raw=None,
            error=error,
            channel=self.resolved.channel_id,
            api=self.resolved.api,
            usage=None,
            metrics=metrics_asdict(
                derive_metrics(
                    TokenUsage(),
                    latency_ms=latency_ms,
                    input_chars=count_request_chars(request),
                    output_chars=0,
                )
            ),
        )

    def _stream_once(
        self,
        *,
        kind: str,
        prepared: Any,
        headers: dict[str, str],
        t0: float,
    ) -> CompletionRecord:
        events: list[dict[str, Any]] = []
        ttft_ms: int | None = None
        try:
            with self._http.stream(
                prepared.method,
                prepared.url,
                json=prepared.body,
                headers=headers,
            ) as resp:
                status = resp.status_code
                if not (200 <= status < 300):
                    raw = resp.read()
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    fake = httpx.Response(status, content=raw, request=resp.request)
                    return self._failure(
                        kind=kind,
                        request=prepared.body,
                        status_code=status,
                        latency_ms=latency_ms,
                        error=_http_error_message(fake),
                    )
                buf = ""
                for chunk in resp.iter_text():
                    buf, new_events = feed_sse(buf, chunk)
                    for event in new_events:
                        if ttft_ms is None and self._event_has_text(event):
                            ttft_ms = int((time.perf_counter() - t0) * 1000)
                        events.append(event)
                for event in flush_sse(buf):
                    if ttft_ms is None and self._event_has_text(event):
                        ttft_ms = int((time.perf_counter() - t0) * 1000)
                    events.append(event)
        except httpx.RequestError:
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        assembled = assemble_stream(self.resolved.api, events)
        usage = self.adapter.parse_token_usage(assembled.payload)
        content = assembled.content or self.adapter.parse_content(assembled.payload)
        metrics = derive_metrics(
            usage,
            latency_ms=latency_ms,
            input_chars=count_request_chars(prepared.body),
            output_chars=count_text_chars(content),
            ttft_ms=ttft_ms,
        )
        return CompletionRecord(
            kind=kind,
            endpoint=self.resolved.base_url,
            model=self.resolved.model,
            request=prepared.body,
            status_code=200,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            content=content,
            reasoning=extract_reasoning(assembled.payload),
            raw=self.adapter.slim_raw(assembled.payload),
            error=None,
            channel=self.resolved.channel_id,
            api=self.resolved.api,
            usage=usage_asdict(usage),
            metrics=metrics_asdict(metrics),
        )

    def _event_has_text(self, event: dict[str, Any]) -> bool:
        return bool(content_delta(self.resolved.api, event))

    def _annotate_stream_metrics(
        self,
        record: CompletionRecord,
        *,
        requested: bool,
        used: bool,
        note: str | None,
    ) -> CompletionRecord:
        metrics = dict(record.metrics or {})
        metrics["stream_requested"] = requested
        metrics["stream_used"] = used
        if note:
            metrics["stream_note"] = note
        record.metrics = metrics
        return record


__all__ = ["ChatClient", "JsonlRecorder", "chat_completions_url"]
