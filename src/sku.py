"""同网关 SKU 卡 / catalog A/B。拆壳与适配器，不进家族栏，不算总分。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.types import Completer, CompletionRecord
from src.usage import http_ok, record_prompt_tokens

SKU_HI = "hi"
SKU_BASE = (
    "You are a helpful assistant. Repeat the following text exactly and add nothing else:\n\n"
)
SKU_EMOJI = "👨‍👩‍👧‍👦 🏳️‍🌈 👍🏽"
SKU_SPECIAL = "<|begin_of_image|>"

_DETAIL_MAX = 240

CatalogStatus = Literal[
    "alias_unlikely",
    "shell_diff",
    "adapter_diff",
    "insufficient",
    "same_shell",
]


@dataclass
class SkuSignal:
    name: str
    prompt_tokens: int | None
    delta: int | None
    http: int | None
    kind: str
    detail: str | None


@dataclass
class SkuCard:
    model_id: str
    hi_prompt_tokens: int | None
    emoji_delta: int | None
    special_image_delta: int | None
    effort_none: SkuSignal
    signals: list[SkuSignal]
    error: str | None


@dataclass
class SkuPeerCompare:
    peer_id: str
    wrapper_offset: int | None
    emoji_delta_peer: int | None
    special_image_delta_peer: int | None
    effort_none_kind: str
    same_emoji: bool | None
    same_effort_kind: bool
    note: str


@dataclass
class CatalogAbResult:
    status: CatalogStatus
    target: SkuCard
    peers: list[SkuPeerCompare]
    cards: list[SkuCard]
    note: str


def measure_sku_card(client: Completer, *, model_id: str) -> SkuCard:
    """打 5 次非流式请求，收 hi / emoji Δ / special Δ / effort=none。"""
    hi_rec = _ask(client, SKU_HI, kind="sku_hi")
    hi_sig = _token_signal("hi", hi_rec)
    hi_pt = hi_sig.prompt_tokens

    base_rec = _ask(client, SKU_BASE, kind="sku_emoji_base")
    emoji_rec = _ask(client, SKU_BASE + SKU_EMOJI, kind="sku_emoji")
    base_sig = _token_signal("emoji_base", base_rec)
    emoji_delta = _subtract(base_sig.prompt_tokens, _trusted_tokens(emoji_rec))
    emoji_sig = _pair_signal(
        "emoji",
        probe=emoji_rec,
        base=base_rec,
        delta=emoji_delta,
    )

    special_rec = _ask(client, SKU_HI + SKU_SPECIAL, kind="sku_special")
    special_delta = _subtract(hi_pt, _trusted_tokens(special_rec))
    special_sig = _pair_signal(
        "special",
        probe=special_rec,
        base=hi_rec,
        delta=special_delta,
    )

    effort_rec = _ask(
        client,
        SKU_HI,
        kind="sku_effort_none",
        extra={"reasoning_effort": "none"},
    )
    effort = _effort_signal(effort_rec)

    error = hi_sig.detail if hi_sig.kind != "ok" else None
    return SkuCard(
        model_id=model_id,
        hi_prompt_tokens=hi_pt,
        emoji_delta=emoji_delta,
        special_image_delta=special_delta,
        effort_none=effort,
        signals=[hi_sig, base_sig, emoji_sig, special_sig, effort],
        error=error,
    )


def compare_sku_cards(target: SkuCard, peers: list[SkuCard]) -> CatalogAbResult:
    """对照目标与同网关具名兄弟。先报 shell_diff，再 adapter_diff / same_shell / insufficient；对不上不猜型号。"""
    compares = [_peer_compare(target, peer) for peer in peers]
    cards = [target, *peers]

    if target.hi_prompt_tokens is None or not peers:
        return _result("insufficient", target, compares, cards)
    if all(row.wrapper_offset is None for row in compares):
        return _result("insufficient", target, compares, cards)

    if any(
        row.wrapper_offset is not None and abs(row.wrapper_offset) >= 1 for row in compares
    ):
        return _result("shell_diff", target, compares, cards)

    if any(_is_adapter_diff(row, target) for row in compares):
        return _result("adapter_diff", target, compares, cards)

    if any(_is_same_shell(row, target, peer) for row, peer in zip(compares, peers)):
        return _result("same_shell", target, compares, cards)

    return _result("insufficient", target, compares, cards)


def run_sku_ab(
    clients: dict[str, Completer],
    *,
    target_id: str,
) -> CatalogAbResult:
    """clients 必须含 target_id；其余当对照。先测目标，再按插入序测对照。不读词表 catalog。"""
    if target_id not in clients:
        raise KeyError(target_id)
    target = measure_sku_card(clients[target_id], model_id=target_id)
    peer_cards = [
        measure_sku_card(client, model_id=mid)
        for mid, client in clients.items()
        if mid != target_id
    ]
    return compare_sku_cards(target, peer_cards)


def format_sku_line(result: CatalogAbResult) -> str:
    """CLI 一行。例：sku=shell_diff hi=37 offset=+24 vs glm-5.3-flash"""
    if result.status == "insufficient":
        return "sku=insufficient"
    parts = [f"sku={result.status}"]
    if result.target.hi_prompt_tokens is not None:
        parts.append(f"hi={result.target.hi_prompt_tokens}")
    peer = _line_peer(result)
    if peer is not None and peer.wrapper_offset is not None:
        parts.append(f"offset={peer.wrapper_offset:+d}")
        parts.append(f"vs {peer.peer_id}")
    return " ".join(parts)


def _ask(
    client: Completer,
    text: str,
    *,
    kind: str,
    extra: dict | None = None,
) -> CompletionRecord:
    return client.complete(
        messages=[{"role": "user", "content": text}],
        temperature=0,
        max_tokens=None,
        extra=extra,
        kind=kind,
        stream=False,
    )


def _trusted_tokens(rec: CompletionRecord) -> int | None:
    if not http_ok(rec):
        return None
    return record_prompt_tokens(rec)


def _subtract(base: int | None, probe: int | None) -> int | None:
    if base is None or probe is None:
        return None
    return probe - base


def _clip_detail(text: str | None) -> str | None:
    if not text:
        return None
    return text[:_DETAIL_MAX]


def _rec_detail(rec: CompletionRecord) -> str | None:
    return _clip_detail(rec.error or rec.content)


def _token_kind(rec: CompletionRecord) -> str:
    if not http_ok(rec):
        return "http_error"
    if record_prompt_tokens(rec) is None:
        return "missing_usage"
    return "ok"


def _token_signal(name: str, rec: CompletionRecord) -> SkuSignal:
    kind = _token_kind(rec)
    return SkuSignal(
        name=name,
        prompt_tokens=_trusted_tokens(rec),
        delta=None,
        http=rec.status_code,
        kind=kind,
        detail=None if kind == "ok" else _rec_detail(rec),
    )


def _pair_signal(
    name: str,
    *,
    probe: CompletionRecord,
    base: CompletionRecord,
    delta: int | None,
) -> SkuSignal:
    if delta is None:
        failed = probe if _token_kind(probe) != "ok" else base
        kind = _token_kind(failed)
        return SkuSignal(
            name=name,
            prompt_tokens=_trusted_tokens(probe),
            delta=None,
            http=failed.status_code,
            kind=kind,
            detail=_rec_detail(failed),
        )
    return SkuSignal(
        name=name,
        prompt_tokens=_trusted_tokens(probe),
        delta=delta,
        http=probe.status_code,
        kind="ok",
        detail=None,
    )


def _effort_body(rec: CompletionRecord) -> str:
    chunks: list[str] = []
    if rec.content:
        chunks.append(rec.content)
    if rec.error:
        chunks.append(rec.error)
    return " ".join(chunks)


def _effort_kind(rec: CompletionRecord) -> str:
    if http_ok(rec):
        return "accepted"
    body = _effort_body(rec)
    if "[1210]" in body or "[1214]" in body:
        return "zhipu_numeric"
    low = body.lower()
    if (
        "thinking-only" in low
        or "cannot be disabled" in low
        or "disabling thinking" in low
    ):
        return "thinking_only"
    return "http_error"


def _effort_signal(rec: CompletionRecord) -> SkuSignal:
    kind = _effort_kind(rec)
    return SkuSignal(
        name="effort_none",
        prompt_tokens=_trusted_tokens(rec),
        delta=None,
        http=rec.status_code,
        kind=kind,
        detail=None if kind == "accepted" else _rec_detail(rec),
    )


def _same_emoji(target: SkuCard, peer: SkuCard) -> bool | None:
    if target.emoji_delta is None or peer.emoji_delta is None:
        return None
    return target.emoji_delta == peer.emoji_delta


def _special_differs(target: SkuCard, peer: SkuCard) -> bool:
    left = target.special_image_delta
    right = peer.special_image_delta
    return left is not None and right is not None and left != right


def _peer_note(target: SkuCard, peer: SkuCard, offset: int | None) -> str:
    if offset is None:
        return f"{peer.model_id} 缺 hi，对不上壳开销"
    if abs(offset) >= 1:
        return f"相对 {peer.model_id}，目标壳开销差 {offset:+d} token，像隐身模板"
    if target.effort_none.kind != peer.effort_none.kind or _special_differs(target, peer):
        return f"相对 {peer.model_id}，壳开销对齐，但 effort 或 special 反应不同"
    return f"相对 {peer.model_id}，壳对齐，不能证明是同一条权重"


def _peer_compare(target: SkuCard, peer: SkuCard) -> SkuPeerCompare:
    if target.hi_prompt_tokens is None or peer.hi_prompt_tokens is None:
        offset: int | None = None
    else:
        offset = target.hi_prompt_tokens - peer.hi_prompt_tokens
    same_emoji = _same_emoji(target, peer)
    same_effort = target.effort_none.kind == peer.effort_none.kind
    return SkuPeerCompare(
        peer_id=peer.model_id,
        wrapper_offset=offset,
        emoji_delta_peer=peer.emoji_delta,
        special_image_delta_peer=peer.special_image_delta,
        effort_none_kind=peer.effort_none.kind,
        same_emoji=same_emoji,
        same_effort_kind=same_effort,
        note=_peer_note(target, peer, offset),
    )


def _is_adapter_diff(row: SkuPeerCompare, target: SkuCard) -> bool:
    if row.wrapper_offset != 0:
        return False
    if not row.same_effort_kind:
        return True
    left = target.special_image_delta
    right = row.special_image_delta_peer
    return left is not None and right is not None and left != right


def _is_same_shell(row: SkuPeerCompare, target: SkuCard, peer: SkuCard) -> bool:
    if row.wrapper_offset != 0:
        return False
    if not row.same_effort_kind:
        return False
    if target.emoji_delta is None and peer.emoji_delta is None:
        return True
    return row.same_emoji is True


def _status_note(status: CatalogStatus) -> str:
    if status == "insufficient":
        return "目标 hi 或对照全缺，不够下结论"
    if status == "shell_diff":
        return "壳开销对不上，像隐身模板，不是直挂别名"
    if status == "adapter_diff":
        return "壳开销能对上，但 effort 或 special token 反应不同"
    if status == "same_shell":
        return "壳对齐，不能证明是同一条权重"
    return "壳或适配器对不上，不像直挂别名"


def _result(
    status: CatalogStatus,
    target: SkuCard,
    peers: list[SkuPeerCompare],
    cards: list[SkuCard],
) -> CatalogAbResult:
    return CatalogAbResult(
        status=status,
        target=target,
        peers=peers,
        cards=cards,
        note=_status_note(status),
    )


def _line_peer(result: CatalogAbResult) -> SkuPeerCompare | None:
    rows = result.peers
    if not rows:
        return None
    if result.status == "shell_diff":
        for row in rows:
            if row.wrapper_offset is not None and abs(row.wrapper_offset) >= 1:
                return row
    if result.status == "adapter_diff":
        for row in rows:
            if row.wrapper_offset == 0 and (
                not row.same_effort_kind
                or (
                    result.target.special_image_delta is not None
                    and row.special_image_delta_peer is not None
                    and result.target.special_image_delta != row.special_image_delta_peer
                )
            ):
                return row
    if result.status == "same_shell":
        for row in rows:
            if row.wrapper_offset == 0:
                return row
    return rows[0]
