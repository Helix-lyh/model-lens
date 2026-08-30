"""官方 max output。只信 catalog/output_limits.yaml，禁止调用方塞小额配额。"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.match import exact_or_longest_prefix


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_output_limits(root: Path | None = None) -> dict[str, int]:
    root = root or repo_root()
    path = root / "catalog" / "output_limits.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("output_limits.yaml 必须是型号 → 官方 max output")
    out: dict[str, int] = {}
    for key, value in data.items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"output_limits.yaml 非法值 {key!r}: {value!r}")
        out[str(key)] = value
    return out


def official_max_output(model: str, limits: dict[str, int] | None = None) -> int | None:
    """精确命中，否则最长前缀（大小写不敏感）。"""
    limits = limits if limits is not None else load_output_limits()
    return exact_or_longest_prefix(model, limits)
