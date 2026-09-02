"""Helpers shared by deterministic structured-answer checkers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable


class DuplicateKey(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKey(key)
        out[key] = value
    return out


def load_payload() -> tuple[dict[str, Any] | None, str | None]:
    raw = Path("payload.txt").read_text(encoding="utf-8")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (json.JSONDecodeError, DuplicateKey, ValueError):
        return None, "json"
    if not isinstance(value, dict):
        return None, "object"
    if not finite(value):
        return None, "finite"
    return value, None


def finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    return True


def exact_keys(value: Any, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys


def strict_int(value: Any) -> bool:
    return type(value) is int


def strict_number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def close(value: Any, expected: float, *, tolerance: float = 1e-9) -> bool:
    return strict_number(value) and abs(float(value) - expected) <= tolerance


def strict_bool(value: Any) -> bool:
    return type(value) is bool


def emit(checks: list[tuple[str, Callable[[dict[str, Any]], bool]]]) -> None:
    data, error = load_payload()
    if data is None:
        for name, _ in checks:
            print("MISS", name)
        print(f"POINTS 0/{len(checks)}")
        return
    earned = 0
    for name, check in checks:
        try:
            ok = bool(check(data))
        except Exception:
            ok = False
        if ok:
            earned += 1
        else:
            print("MISS", name)
    print(f"POINTS {earned}/{len(checks)}")
