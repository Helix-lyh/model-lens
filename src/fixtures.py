"""Constrained resolution for executable bank fixtures."""

from __future__ import annotations

from pathlib import Path


def resolve_fixture_path(
    root: Path,
    rel: object,
    *,
    question_id: str = "",
) -> Path:
    """Resolve a fixture below ``bank/tests`` without following in-tree symlinks."""
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError(f"{question_id} tests_file 缺失")
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{question_id} tests_file 路径越界: {rel}")

    raw_path = root / candidate
    probe = root
    for part in candidate.parts:
        probe = probe / part
        if probe.is_symlink():
            raise ValueError(f"{question_id} tests_file 不得经过 symlink: {rel}")

    normalized = raw_path.resolve(strict=False)
    allowed = (root / "bank" / "tests").resolve(strict=False)
    try:
        normalized.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(
            f"{question_id} tests_file 必须位于 bank/tests: {rel}"
        ) from exc
    if not normalized.is_file():
        raise ValueError(f"{question_id} tests file not found: {rel}")
    return normalized
