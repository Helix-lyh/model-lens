"""精确命中，否则最长前缀（大小写不敏感）。catalog 与 limits 共用。"""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def exact_or_longest_prefix(key: str, mapping: dict[str, T]) -> T | None:
    key = key.strip()
    if not key:
        return None
    if key in mapping:
        return mapping[key]
    folded = {k.casefold(): v for k, v in mapping.items()}
    if key.casefold() in folded:
        return folded[key.casefold()]
    best: T | None = None
    best_len = 0
    for raw, value in mapping.items():
        needle = raw.casefold()
        if key.casefold().startswith(needle) and len(needle) > best_len:
            best = value
            best_len = len(needle)
    return best
