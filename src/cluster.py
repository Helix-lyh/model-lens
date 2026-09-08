"""编码题 raw cluster 身份。bank / compare / gallery / report 共用。"""

from __future__ import annotations

from typing import Any

from src.toolchain import CODE_LANGS


def language_of(language: str | None, question_id: str) -> str | None:
    if language in CODE_LANGS:
        return str(language)
    for lang in CODE_LANGS:
        if question_id.endswith(f"-{lang}"):
            return lang
    return None


def cluster_id_of(
    *,
    question_id: str,
    raw_id: Any = None,
    cluster_id: Any = None,
    language: str | None = None,
    prefer: str = "cluster",
) -> str:
    """语言变体折回同一 raw cluster。prefer=raw 时 raw_id 优先于 cluster_id。"""
    if prefer == "raw":
        explicit = raw_id or cluster_id
    else:
        explicit = cluster_id or raw_id
    if explicit:
        return str(explicit)
    qid = str(question_id or "")
    lang = language_of(language, qid)
    return qid.rsplit("-", 1)[0] if lang and qid else qid


def cluster_id_from_row(row: dict[str, Any], *, prefer: str = "cluster") -> str | None:
    qid = str(row.get("question_id") or "")
    raw_id = row.get("raw_id")
    cluster_id = row.get("cluster_id")
    if not qid and not raw_id and not cluster_id:
        return None
    key = cluster_id_of(
        question_id=qid,
        raw_id=raw_id,
        cluster_id=cluster_id,
        language=row.get("language") if isinstance(row.get("language"), str) else None,
        prefer=prefer,
    )
    return key or None


def raw_matrix_from_bank(bank: dict[str, Any]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    seen: set[str] = set()
    for row in bank.get("questions") or []:
        if not isinstance(row, dict):
            continue
        raw = cluster_id_from_row(row)
        domain = row.get("domain")
        difficulty = row.get("difficulty")
        if not raw or not domain or not difficulty or raw in seen:
            continue
        seen.add(raw)
        matrix.setdefault(str(domain), {}).setdefault(str(difficulty), 0)
        matrix[str(domain)][str(difficulty)] += 1
    return matrix

