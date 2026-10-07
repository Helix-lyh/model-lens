"""题目插件注册表。

新增题提供一个 descriptor 并注册。运行器通过本模块解析 prompt、scorer 和可选 runtime profile。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


PromptFn = Callable[[str | None], str]
ScoreFn = Callable[[str, str | None], dict[str, Any]]


@dataclass(frozen=True)
class ItemPlugin:
    item_id: str
    domain: str
    title: str
    prompt_fn: PromptFn
    score_fn: ScoreFn
    points_total: int = 20
    runtime_profiles: Mapping[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    def prompt(self, language: str | None = None) -> str:
        return self.prompt_fn(language)

    def score(self, text: str, language: str | None = None) -> dict[str, Any]:
        return self.score_fn(text, language)


class ItemRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ItemPlugin] = {}

    def register(self, item: ItemPlugin, *, replace: bool = False) -> None:
        if not item.item_id or item.item_id in self._items and not replace:
            raise ValueError(f"duplicate or empty item id: {item.item_id!r}")
        if item.domain not in {"coding", "engineering", "reasoning"}:
            raise ValueError(f"unsupported item domain: {item.domain}")
        self._items[item.item_id] = item

    def get(self, item_id: str) -> ItemPlugin:
        try:
            return self._items[item_id]
        except KeyError as exc:
            raise LookupError(f"unknown item: {item_id}") from exc

    def resolve(self, item_id: str) -> ItemPlugin:
        """Resolve an item through the registry's public lookup boundary."""
        return self.get(item_id)

    def items(self, domain: str | None = None) -> tuple[ItemPlugin, ...]:
        values = self._items.values()
        if domain is not None:
            values = (item for item in values if item.domain == domain)
        return tuple(values)

    def __contains__(self, item_id: str) -> bool:
        return item_id in self._items


ITEMS = ItemRegistry()


def register(item: ItemPlugin) -> ItemPlugin:
    ITEMS.register(item)
    return item
