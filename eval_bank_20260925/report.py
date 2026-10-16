"""活跃题库的统一报告。

阶段分、题目分、题库分都是各自满分上的百分数。编码、工程、推理分栏列出，
不合成一个跨栏总分。
"""

from __future__ import annotations

from typing import Any

from eval_bank_20260925.evaluation import aggregate_groups, is_judged, summarize, summarize_engineering
from eval_bank_20260925.bank_manifest import ACTIVE_VERSION
from eval_bank_20260925.next_reasoning import reasoning_group_maxes


def _stage_text(row: dict[str, Any]) -> str:
    groups = row.get("groups")
    if isinstance(groups, list) and groups:
        parts = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            name = group.get("name") or "-"
            percent = group.get("percent")
            got, maximum = group.get("points"), group.get("max")
            if percent is None:
                parts.append(str(name))
            else:
                parts.append(f"{name} {percent}（{got}/{maximum}）")
        return "；".join(parts)
    if row.get("positive_percent") is not None:
        return (
            f"得分点 {row.get('positive_points')}/{row.get('points_total')}；"
            f"扣分点 {row.get('negative_points')}/{row.get('points_total')}；"
            f"没测到 {int(row.get('points_total') or 0) - int(row.get('positive_points') or 0) - int(row.get('negative_points') or 0)}"
        )
    return "-"


def outcome_label(row: dict[str, Any]) -> str | None:
    """未判行在报告里的中文标记；固定分母口径下都记 0 分。"""
    if row.get("reason_code") == "response_truncated" or row.get("truncated") is True:
        return "截断（0分）"
    if is_judged(row):
        return None
    reason = row.get("reason_code")
    if reason in {"timeout"}:
        return "超时（0分）"
    if reason in {"grader_error", "grader_timeout", "scorer_error", "missing_toolchain", "runtime_error"}:
        return "判分环境错误（0分）"
    if row.get("status") == "missing":
        return "缺失（0分）"
    if row.get("status") == "pending_review":
        return "待复核（0分）"
    return "错误（0分）"


def _final_text(row: dict[str, Any]) -> str:
    label = outcome_label(row)
    if label is not None:
        return f"{label}（0/{row.get('points_total') or 20}）"
    percent = row.get("score_percent")
    if percent is None:
        return "-"
    return f"{percent}（{row.get('points')}/{row.get('points_total')}）"


def bank_rows(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get("bank_id") or "unscoped", []).append(row)
    return list(grouped.items())


def mean_percent(rows: list[dict[str, Any]]) -> float | None:
    values = [float(row["score_percent"]) for row in rows if is_judged(row) and isinstance(row.get("score_percent"), (int, float)) and not isinstance(row.get("score_percent"), bool)]
    return round(sum(values) / len(values), 1) if values else None


def _domain(row: dict[str, Any]) -> str:
    bank_id = row.get("bank_id")
    if bank_id == "business-coding":
        return "coding"
    if bank_id == "business-engineering":
        return "engineering"
    if bank_id == "business-reasoning":
        return "reasoning"
    item_id = str(row.get("item") or "")
    if item_id.startswith("E-"):
        return "engineering"
    if item_id.startswith(("CP-", "P-")):
        return "coding"
    return "reasoning"


def _with_groups(row: dict[str, Any], groups: list[dict[str, Any]]) -> dict[str, Any]:
    return {**row, "groups": [dict(group) for group in groups]}


def _number(value: Any) -> bool:
    return type(value) in (int, float)


def _engineering_groups(row: dict[str, Any]) -> list[dict[str, Any]] | None:
    """没测到是满分里尚未观测的部分。缺这三项的已判行不补 0。"""
    positive = row.get("positive_points")
    negative = row.get("negative_points")
    total = row.get("points_total")
    if not all(_number(value) for value in (positive, negative, total)):
        return None
    return [
        {"name": "得分点", "points": positive, "max": total},
        {"name": "扣分点", "points": negative, "max": total},
        {"name": "没测到", "points": total - positive - negative, "max": total},
    ]


def _rows_for_group_table(domain: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """已判但没有可用 groups 时补满分，避免 0 分题把分组百分比抬高。"""
    prepared: list[dict[str, Any]] = []
    coding_zeros = [{"name": f"g{index}", "points": 0, "max": 4} for index in range(1, 6)]
    for row in rows:
        if not is_judged(row):
            continue
        if domain == "engineering":
            groups = _engineering_groups(row)
            prepared.append(_with_groups(row, groups) if groups is not None else row)
            continue
        if aggregate_groups([row]):
            prepared.append(row)
            continue
        if domain == "coding":
            prepared.append(_with_groups(row, coding_zeros))
        elif domain == "reasoning":
            bounds = reasoning_group_maxes(row.get("item"))
            if bounds:
                prepared.append(_with_groups(row, [{"name": name, "points": 0, "max": maximum} for name, maximum in bounds]))
            else:
                prepared.append(row)
        else:
            prepared.append(row)
    return prepared


def _channels(rows: list[dict[str, Any]], meta: dict[str, Any]) -> list[str]:
    ordered = [name for name in (meta.get("models") or []) if any(row.get("channel") == name for row in rows)]
    for row in rows:
        name = row.get("channel") or "-"
        if name not in ordered:
            ordered.append(name)
    return ordered


def _channel_section(name: str, rows: list[dict[str, Any]], pass_k: int) -> list[str]:
    lines = [
        f"## 渠道 {name}",
        "",
        "| 题库 | 版本 | 作答 | 已判 | 通过 | 截断 | 固定分母平均分 | 已判平均分 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for bank_id, bank in bank_rows(rows):
        judged = [row for row in bank if is_judged(row)]
        passed = sum(row.get("passed") is True for row in judged)
        truncated = sum(outcome_label(row) == "截断（0分）" for row in bank)
        version = next((row.get("bank_version") for row in bank if row.get("bank_version")), "-")
        fixed_mean = round(sum(float(row["score_percent"]) for row in judged if isinstance(row.get("score_percent"), (int, float))) / len(bank), 1) if bank else None
        judged_mean = mean_percent(bank)
        lines.append(
            f"| {bank_id} | {version} | {len(bank)} | {len(judged)} | {passed} | {truncated} | "
            f"{fixed_mean if fixed_mean is not None else '-'} | {judged_mean if judged_mean is not None else '-'} |"
        )
    lines += [
        "",
        "### 三栏汇总",
        "",
        "| 栏目 | 已判/作答 | 累计得分 | 固定满分 | 得分百分比（固定分母） | 已判满分 | 已判百分比（辅助） | 截断 | 超时 | 其他未判 | 严格通过 | pass@1 | pass@k |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    by_domain: dict[str, list[dict[str, Any]]] = {domain: [] for domain in ("coding", "engineering", "reasoning")}
    for row in rows:
        by_domain[_domain(row)].append(row)
    for domain, domain_rows in by_domain.items():
        if not domain_rows:
            continue
        if domain == "engineering":
            stats = summarize_engineering(domain_rows, pass_k=pass_k)
            earned, percent, judged_percent = stats["net_points"], stats["net_percent_total"], stats["judged_net_percent_total"]
            strict_passed = stats["strict_passed"]
        else:
            stats = summarize(domain_rows, pass_k=pass_k)
            earned, percent, judged_percent = stats["points"], stats["score_percent_total"], stats["judged_score_percent_total"]
            strict_passed = stats["passed"]
        other = stats["attempted"] - stats["judged"] - stats["truncated"] - sum(
            row.get("reason_code") == "timeout" and not is_judged(row) for row in domain_rows
        )
        lines.append(
            f"| {domain} | {stats['judged']}/{stats['attempted']} | {earned:g} | {stats['points_total']:g} | "
            f"{f'{percent}%' if percent is not None else '-'} | {stats['judged_points_total']:g} | "
            f"{f'{judged_percent}%' if judged_percent is not None else '-'} | {stats['truncated']} | {stats['timeouts']} | {max(other, 0)} | "
            f"{strict_passed} | {stats['pass_at_1'] if stats['pass_at_1'] is not None else '-'} | "
            f"{stats['pass_at_k'] if stats['pass_at_k'] is not None else '-'} (k={pass_k}) |"
        )
    lines += [
        "",
        "### 分组累计",
        "",
        "| 栏目 | 题库 | 版本 | 分组 | 得分 | 满分 | 百分比 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for domain, domain_rows in by_domain.items():
        for group in aggregate_groups(_rows_for_group_table(domain, domain_rows)):
            lines.append(
                f"| {domain} | {group['bank_id']} | {group['bank_version']} | {group['name']} | "
                f"{group['points']:g} | {group['max']:g} | {group['percent']}% |"
            )
    lines.append("")
    return lines


def render_markdown(meta: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    pass_k = int(meta.get("pass_k") or meta.get("pass_at_k") or 1)
    lines = [
        f"# 评测报告 · {meta.get('experiment_id') or ''} · 版本 {meta.get('bank_version') or ACTIVE_VERSION}" + (f" · 计分 {meta['scoring_version']}" if meta.get('scoring_version') else ""),
        "",
        "每个渠道单独成节，不跨模型合计。主口径是固定分母：每次作答按满分进分母，截断、超时、错误、缺失都记 0 分；"
        "“已判百分比”是辅助口径，只除以已判题目的满分。编码、工程、推理分开，没有跨栏总分。",
        f"阶段：{meta.get('phase', '-')}。语言：{','.join(meta.get('langs') or []) or '-'}。采样 {meta.get('samples', 1)} 次。",
        "",
    ]
    for name in _channels(rows, meta):
        lines += _channel_section(name, [row for row in rows if (row.get("channel") or "-") == name], pass_k)
    lines += [
        "## 逐题",
        "",
        "状态列保留原始判定：`pass`／`fail` 是模型判分结果；`error` 等未判状态在固定分母口径下记 0 分，最终得分列写明原因（如“截断（0分）”）。"
        "分组累计只统计已判题；已判但没有可用分组的编码、推理按 0 分计入原分组满分；工程题使用得分点、扣分点、没测到。",
        "",
        "| 题库 | 渠道 | 题 | 语言 | 采样 | 状态 | 阶段分 | 最终得分 | 原因 |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in sorted(rows, key=lambda item: (item.get("channel") or "", item.get("bank_id") or "", item.get("item") or "", item.get("lang") or "", item.get("sample") or 0)):
        lines.append(
            f"| {row.get('bank_id') or '-'} | {row.get('channel')} | {row.get('item')} | {row.get('lang') or '-'} | "
            f"{row.get('sample') or 0} | {row.get('status')} | {_stage_text(row)} | {_final_text(row)} | {row.get('reason_code') or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)
