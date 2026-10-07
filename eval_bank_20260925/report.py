"""活跃题库的统一报告。

阶段分、题目分、题库分都是各自满分上的百分数。编码、工程、推理分栏列出，
不合成一个跨栏总分。
"""

from __future__ import annotations

from typing import Any

from eval_bank_20260925.evaluation import aggregate_groups, is_judged, summarize, summarize_engineering


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


def _final_text(row: dict[str, Any]) -> str:
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


def render_markdown(meta: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# 评测报告 · {meta.get('experiment_id') or ''} · 版本 {meta.get('bank_version') or '20261008'}",
        "",
        "各栏百分数只除以本栏已判题目的满分。missing、error、pending_review 不进分母，也不记 0。编码、工程、推理分开，没有跨栏总分。",
        f"阶段：{meta.get('phase', '-')}。语言：{','.join(meta.get('langs') or []) or '-'}。采样 {meta.get('samples', 1)} 次。",
        "",
        "## 题库",
        "",
        "| 题库 | 版本 | 已判 | 通过 | 通过率 | 平均分 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for bank_id, bank in bank_rows(rows):
        judged = [row for row in bank if is_judged(row)]
        passed = sum(row.get("passed") is True for row in judged)
        rate = round(passed / len(judged), 4) if judged else None
        version = next((row.get("bank_version") for row in bank if row.get("bank_version")), "-")
        lines.append(
            f"| {bank_id} | {version} | {len(judged)} | {passed} | {rate if rate is not None else '-'} | {mean_percent(bank) if mean_percent(bank) is not None else '-'} |"
        )
    lines += [
        "",
        "## 三栏汇总",
        "",
        "跨题累计分只加已判题目，未判不进这一栏的满分。pass@k 在题目与语言的分组内估计。",
        "",
        "| 栏目 | 已判/尝试 | 累计得分 | 已判满分 | 得分百分比 | 严格通过 | pass@1 | pass@k |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    pass_k = int(meta.get("pass_k") or meta.get("pass_at_k") or 1)
    by_domain: dict[str, list[dict[str, Any]]] = {name: [] for name in ("coding", "engineering", "reasoning")}
    for row in rows:
        by_domain[_domain(row)].append(row)
    for domain, domain_rows in by_domain.items():
        if not domain_rows:
            continue
        stats = summarize_engineering(domain_rows, pass_k=pass_k) if domain == "engineering" else summarize(domain_rows, pass_k=pass_k)
        if domain == "engineering":
            earned, maximum, percent = stats["net_points"], stats["points_total"], stats["net_percent_total"]
            strict_passed = stats["strict_passed"]
        else:
            earned, maximum, percent = stats["points"], stats["points_total"], stats["score_percent_total"]
            strict_passed = stats["passed"]
        percent_text = f"{percent}%" if percent is not None else "-"
        pass1 = stats["pass_at_1"] if stats["pass_at_1"] is not None else "-"
        passk = stats["pass_at_k"] if stats["pass_at_k"] is not None else "-"
        lines.append(
            f"| {domain} | {stats['judged']}/{stats['attempted']} | {earned:g} | {maximum:g} | {percent_text} | "
            f"{strict_passed} | {pass1} | {passk} (k={pass_k}) |"
        )
    lines += [
        "",
        "## 分组累计",
        "",
        "分组只在同一题库与版本内累计；工程题使用正分、负分、净分账。",
        "",
        "| 栏目 | 题库 | 版本 | 分组 | 得分 | 满分 | 百分比 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for domain, domain_rows in by_domain.items():
        for group in aggregate_groups([row for row in domain_rows if is_judged(row)]):
            lines.append(
                f"| {domain} | {group['bank_id']} | {group['bank_version']} | {group['name']} | "
                f"{group['points']:g} | {group['max']:g} | {group['percent']}% |"
            )
    lines += [
        "",
        "## 逐题",
        "",
        "状态列：`pass`／`fail` 是模型判分结果；`missing`、`error`、`pending_review` 不进分母、不记 0 分。",
        "原因列：`ok` 满分。`tests_failed` 是编码未满分，`describe_invalid` 和 `envelope_mismatch` 记 0 分，三者都进分母。`content_mismatch` 在推理里是字段齐全但未满分，在工程里是关系账未满分。`schema_mismatch` 按已得分进分母，`format_error` 记 0 分进分母。`execution_error` 在 missing 时不进分母，在 fail 时记 0 分进分母。`missing_toolchain`、`missing_fence`、`grader_error`、`scorer_error`、`runtime_error` 不进分母、不记 0。`timeout` 和 `timeout_partial` 是已判失败，进分母。",
        "",
        "| 题库 | 渠道 | 题 | 语言 | 状态 | 阶段分 | 最终得分 | 原因 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(rows, key=lambda item: (item.get("bank_id") or "", item.get("channel") or "", item.get("item") or "", item.get("lang") or "", item.get("sample") or 0)):
        lines.append(
            f"| {row.get('bank_id') or '-'} | {row.get('channel')} | {row.get('item')} | {row.get('lang') or '-'} | "
            f"{row.get('status')} | {_stage_text(row)} | {_final_text(row)} | {row.get('reason_code') or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)
