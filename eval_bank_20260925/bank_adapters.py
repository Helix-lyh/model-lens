"""Pluggable boundaries between bank definitions, prompts and scorers."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


class BankAdapter(Protocol):
    def prompt(self, item: Any, language: str | None = None) -> str: ...

    def score(self, item: Any, text: str, language: str | None = None) -> dict[str, Any]: ...

    def fingerprint(self, adapter_id: str) -> str: ...


@dataclass(frozen=True)
class FunctionalAdapter:
    prompt_fn: Callable[[Any, str | None], str]
    score_fn: Callable[[Any, str, str | None], dict[str, Any]]
    scorer_sources: tuple[str, ...] = ()

    def prompt(self, item: Any, language: str | None = None) -> str:
        return self.prompt_fn(item, language)

    def score(self, item: Any, text: str, language: str | None = None) -> dict[str, Any]:
        return self.score_fn(item, text, language)

    def fingerprint(self, adapter_id: str) -> str:
        return _fingerprint(adapter_id, self.scorer_sources)


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BankAdapter] = {}

    def register(self, adapter_id: str, adapter: BankAdapter, *, replace: bool = False) -> None:
        if not adapter_id:
            raise ValueError("adapter_id must be non-empty")
        if adapter_id in self._adapters and not replace:
            raise ValueError(f"adapter already registered: {adapter_id}")
        self._adapters[adapter_id] = adapter

    def resolve(self, adapter_id: str) -> BankAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise LookupError(f"unknown bank adapter: {adapter_id}") from exc

    def fingerprint(self, adapter_id: str) -> str:
        adapter = self.resolve(adapter_id)
        method = getattr(adapter, "fingerprint", None)
        if method is None:
            raise TypeError(f"adapter does not expose a scorer fingerprint: {adapter_id}")
        return method(adapter_id)

    def __contains__(self, adapter_id: str) -> bool:
        return adapter_id in self._adapters

    @property
    def adapter_ids(self) -> frozenset[str]:
        return frozenset(self._adapters)


ADAPTERS = AdapterRegistry()


def _item_adapter_id(item: Any) -> str:
    from .bank_manifest import adapter_for_item

    return adapter_for_item(item.id)


def adapter_for(item: Any) -> BankAdapter:
    return ADAPTERS.resolve(_item_adapter_id(item))


def scorer_fingerprint(item: Any) -> str:
    return ADAPTERS.fingerprint(_item_adapter_id(item))


def adapter_id_for(item: Any) -> str:
    return _item_adapter_id(item)


def render_item_prompt(item: Any, language: str | None = None) -> str:
    from .bank_registry import ITEMS
    if item.id in ITEMS:
        return ITEMS.resolve(item.id).prompt(language)
    from .bank_manifest import ACTIVE_ITEMS
    if item.id in ACTIVE_ITEMS:
        raise RuntimeError(f"active item is not registered: {item.id}")
    return adapter_for(item).prompt(item, language)


def score_item_with_adapter(item: Any, text: str, language: str | None = None) -> dict[str, Any]:
    from .bank_registry import ITEMS
    if item.id in ITEMS:
        return ITEMS.resolve(item.id).score(text, language)
    from .bank_manifest import ACTIVE_ITEMS
    if item.id in ACTIVE_ITEMS:
        raise RuntimeError(f"active item is not registered: {item.id}")
    return adapter_for(item).score(item, text, language)


def _plugin_prompt(item: Any, language: str | None) -> str:
    from .bank_registry import ITEMS

    return ITEMS.resolve(item.id).prompt(language)


def _plugin_score(item: Any, text: str, language: str | None) -> dict[str, Any]:
    from .bank_registry import ITEMS

    return ITEMS.resolve(item.id).score(text, language)


_CODING_SOURCES = (
    "eval_bank_20260925/bank_adapters.py",
    "eval_bank_20260925/next_coding.py",
    "eval_bank_20260925/coding_score.py",
    "eval_bank_20260925/coding_facts.py",
    "eval_bank_20260925/describe_contract.py",
    "eval_bank_20260925/runtime_profiles.py",
    "src/grade.py",
)
_ENGINEERING_SOURCES = (
    "eval_bank_20260925/bank_adapters.py",
    "eval_bank_20260925/engineering.py",
    "eval_bank_20260925/engineering_extra.py",
    "eval_bank_20260925/engineering_next.py",
    "src/grade.py",
)
_REASONING_SOURCES = (
    "eval_bank_20260925/bank_adapters.py",
    "eval_bank_20260925/next_reasoning.py",
    "eval_bank_20260925/score.py",
)


def install_builtin_adapters() -> None:
    builtins = {
        "coding": FunctionalAdapter(_plugin_prompt, _plugin_score, _CODING_SOURCES),
        "engineering": FunctionalAdapter(_plugin_prompt, _plugin_score, _ENGINEERING_SOURCES),
        "reasoning": FunctionalAdapter(_plugin_prompt, _plugin_score, _REASONING_SOURCES),
    }
    for adapter_id, adapter in builtins.items():
        if adapter_id not in ADAPTERS:
            ADAPTERS.register(adapter_id, adapter)


def validate_manifest_adapters() -> None:
    """Fail during startup when a bank points at an uninstalled adapter."""
    from .bank_manifest import ACTIVE_ITEMS, BANKS

    configured = {bank.adapter_id for bank in BANKS}
    missing = configured - ADAPTERS.adapter_ids
    if missing:
        raise LookupError(f"manifest references unregistered adapters: {sorted(missing)}")
    from .bank_registry import ITEMS

    unregistered = [item_id for item_id in ACTIVE_ITEMS if item_id not in ITEMS]
    if unregistered:
        raise LookupError(f"active items are not registered: {unregistered}")
    from .runtime_profiles import validate_manifest_profiles

    validate_manifest_profiles()


@lru_cache(maxsize=None)
def _fingerprint(adapter_id: str, sources: tuple[str, ...]) -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256(adapter_id.encode())
    for relative in sources:
        path = root / relative
        digest.update(relative.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


install_builtin_adapters()
from . import plugins  # noqa: E402,F401
from .runtime_profiles import install_manifest_profiles  # noqa: E402

install_manifest_profiles()
validate_manifest_adapters()
