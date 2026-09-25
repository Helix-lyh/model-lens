#!/usr/bin/env python3
"""合并多场 run_eval_20260925 结果并出对比表。

同一个 (channel, item, lang, sample) 的有效结果不会被错误补跑覆盖；同等级取后一次。
用法：
  .venv/bin/python cursor_workspace/build_scripts/merge_eval_20260925.py out/eval-...-quick out/eval-...-retry
"""

from __future__ import annotations

import json
import math
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from eval_bank_20260925.catalog import BY_ID  # noqa: E402
from eval_bank_20260925.challenge_coding import coding_items  # noqa: E402

LEVELS = ("easy", "medium", "hard", "extreme")
ALL_BY_ID = {**BY_ID, **{item.id: item for item in coding_items()}}


def _prefer(existing: dict, incoming: dict) -> dict:
    """重跑时错误/缺失不能覆盖已有的有效判定；同等级仍以后一次为准。"""
    old_status = str(existing.get("status"))
    new_status = str(incoming.get("status"))
    if old_status in {"pass", "fail"} and new_status in {"error", "missing"}:
        return existing
    if new_status in {"pass", "fail"} and old_status in {"error", "missing"}:
        return incoming
    return incoming


def _key(row: dict) -> tuple:
    sample = row.get("sample")
    run_id = row.get("run_id")
    # Legacy single-sample rows retain the old key shape for callers that
    # consume merged results directly.
    if run_id is not None:
        return (row["channel"], row["item"], row.get("lang"), run_id, int(sample or 0))
    if sample in (None, 0):
        return (row["channel"], row["item"], row.get("lang"))
    return (row["channel"], row["item"], row.get("lang"), int(sample))


def load(dirs: list[Path]) -> dict[tuple, dict]:
    merged: dict[tuple, dict] = {}
    for d in dirs:
        f = d / "results.jsonl"
        if not f.is_file():
            print(f"warn: {f} 不存在，跳过", file=sys.stderr)
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"warn: {f} 无法解析 JSON（{exc.msg}），跳过该行", file=sys.stderr)
                continue
            if not isinstance(row, dict) or not row.get("channel") or not row.get("item"):
                print(f"warn: {f}:{line[:80]} schema 无 channel/item，跳过", file=sys.stderr)
                continue
            key = _key(row)
            merged[key] = _prefer(merged[key], row) if key in merged else row
    return merged


def pass_at_k(rows: list[dict], k: int) -> float | None:
    if k < 1:
        raise ValueError("pass_at_k requires k >= 1")
    grouped: dict[tuple[str, str | None], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["item"], row.get("lang")), []).append(row)
    estimates = []
    for samples in grouped.values():
        judged = [r for r in samples if r.get("status") in {"pass", "fail"}]
        n = len(judged)
        if n < k:
            continue
        c = sum(r.get("passed") is True for r in judged)
        estimate = 1.0 if c == n or n - c < k else 0.0 if c == 0 else 1.0 - math.comb(n - c, k) / math.comb(n, k)
        estimates.append(estimate)
    return round(sum(estimates) / len(estimates), 4) if estimates else None


def bucket(rows: list[dict], pass_k: int = 1) -> dict:
    judged = [r for r in rows if r["status"] in ("pass", "fail")]
    passed = [r for r in judged if r.get("passed") is True]
    missing = [r for r in rows if r["status"] == "missing"]
    errors = [r for r in rows if r["status"] == "error"]
    numeric = [r for r in judged if r.get("score10") is not None]
    mean = round(sum(float(r["score10"]) for r in numeric) / len(numeric), 4) if numeric else None
    return {
        "judged": len(judged),
        "pass": len(passed),
        "pass_at_1": pass_at_k(rows, 1),
        "pass_at_k": pass_at_k(rows, pass_k),
        "mean_score10": mean,
        "missing": len(missing),
        "error": len(errors),
        "pending_review": sum(r.get("status") == "pending_review" for r in rows),
    }


def _level(item_id: str) -> str:
    item = ALL_BY_ID.get(item_id)
    return getattr(item, "level", "unknown")


def _domain(item_id: str) -> str:
    item = ALL_BY_ID.get(item_id)
    if item is None:
        return "unknown"
    return "coding" if getattr(item, "kind", None) == "coding" or getattr(item, "reference", None) else "reasoning"


def _render(rows: list[dict], pass_k: int = 1) -> str:
    channels = sorted({r["channel"] for r in rows})
    lines = ["## 总览", "", "| channel | judged | pass | pass@1 | pass@k | mean score10 | missing | error | pending |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for ch in channels:
        b = bucket([r for r in rows if r["channel"] == ch], pass_k)
        lines.append(f"| {ch} | {b['judged']} | {b['pass']} | {b['pass_at_1']} | {b['pass_at_k']} | {b['mean_score10']} | {b['missing']} | {b['error']} | {b['pending_review']} |")
    lines += ["", "## 分难度", "", "| channel | " + " | ".join(LEVELS) + " |", "| --- | " + " | ".join("---" for _ in LEVELS) + " |"]
    for ch in channels:
        cells = []
        for lv in LEVELS:
            sub = [r for r in rows if r["channel"] == ch and _level(r["item"]) == lv]
            b = bucket(sub)
            cells.append(f"{b['pass']}/{b['judged']}" if b["judged"] else "—")
        lines.append(f"| {ch} | " + " | ".join(cells) + " |")
    lines += ["", "## 分域", "", "| channel | reasoning | coding |", "| --- | --- | --- |"]
    for ch in channels:
        cells = []
        for domain in ("reasoning", "coding"):
            b = bucket([r for r in rows if r["channel"] == ch and _domain(r["item"]) == domain])
            cells.append(f"{b['pass']}/{b['judged']}" if b["judged"] else "—")
        lines.append(f"| {ch} | " + " | ".join(cells) + " |")
    lines += ["", "## 逐题矩阵", "", "| item | level | " + " | ".join(channels) + " |", "| --- | --- | " + " | ".join("---" for _ in channels) + " |"]
    items = sorted({r["item"] for r in rows}, key=lambda i: (LEVELS.index(_level(i)) if _level(i) in LEVELS else len(LEVELS), i))
    for item in items:
        cells = []
        for ch in channels:
            hits = [r for r in rows if r["channel"] == ch and r["item"] == item]
            parts = []
            for r in sorted(hits, key=lambda x: x.get("lang") or ""):
                status = r.get("status")
                if status == "pass": parts.append("P")
                elif status == "fail": parts.append(str(r.get("score10")))
                elif status == "error": parts.append("E")
                elif status == "missing": parts.append("M")
                elif status == "pending_review": parts.append("R")
                else: parts.append("?")
            cells.append("/".join(parts) if parts else "—")
        lines.append(f"| {item} | {_level(item)} | " + " | ".join(cells) + " |")
    bad = [r for r in rows if r.get("status") in ("error", "missing")]
    if bad:
        lines += ["", "## 异常明细", ""]
        lines.extend(f"- {r.get('channel')} {r.get('item')} {r.get('lang') or ''}: {r.get('status')} {r.get('reason_code')} {r.get('detail') or ''}" for r in sorted(bad, key=lambda x: (x.get("channel", ""), x.get("item", ""))))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dirs", nargs="+", help="run_eval 输出目录；重复目录会去重")
    parser.add_argument("--out", type=Path, default=None, help="可选：落盘 merged results/summary")
    parser.add_argument("--pass-at", type=int, default=1, dest="pass_k", help="报告 pass@k")
    args = parser.parse_args(argv)
    dirs = list(dict.fromkeys(Path(p) for p in args.dirs))
    if not dirs:
        print(__doc__)
        return 2
    if args.pass_k < 1:
        parser.error("--pass-at 必须 >= 1")
    rows = list(load(dirs).values())
    channels = sorted({r["channel"] for r in rows})

    print("\n## 总览\n")
    print("| channel | judged | pass | pass@1 | pass@k | mean score10 | missing | error | pending |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for ch in channels:
        b = bucket([r for r in rows if r["channel"] == ch], args.pass_k)
        print(f"| {ch} | {b['judged']} | {b['pass']} | {b['pass_at_1']} | {b['pass_at_k']} | {b['mean_score10']} | {b['missing']} | {b['error']} | {b['pending_review']} |")

    print("\n## 分难度\n")
    print("| channel | " + " | ".join(LEVELS) + " |")
    print("| --- | " + " | ".join("---" for _ in LEVELS) + " |")
    for ch in channels:
        cells = []
        for lv in LEVELS:
            sub = [r for r in rows if r["channel"] == ch and _level(r["item"]) == lv]
            b = bucket(sub)
            cells.append(f"{b['pass']}/{b['judged']}" if b["judged"] else "—")
        print(f"| {ch} | " + " | ".join(cells) + " |")

    print("\n## 分域\n")
    print("| channel | reasoning | coding |")
    print("| --- | --- | --- |")
    for ch in channels:
        cells = []
        for is_reasoning in (True, False):
            domain = "reasoning" if is_reasoning else "coding"
            sub = [r for r in rows if r["channel"] == ch and _domain(r["item"]) == domain]
            b = bucket(sub)
            cells.append(f"{b['pass']}/{b['judged']}" if b["judged"] else "—")
        print(f"| {ch} | " + " | ".join(cells) + " |")

    print("\n## 逐题矩阵（P=pass，分=score10，E=error，M=missing，—=未跑）\n")
    header = "| item | level | " + " | ".join(channels) + " |"
    print(header)
    print("| --- | --- | " + " | ".join("---" for _ in channels) + " |")
    items = sorted({r["item"] for r in rows}, key=lambda i: (LEVELS.index(_level(i)) if _level(i) in LEVELS else len(LEVELS), i))
    for item in items:
        cells = []
        for ch in channels:
            hits = [r for r in rows if r["channel"] == ch and r["item"] == item]
            if not hits:
                cells.append("—")
                continue
            parts = []
            for r in sorted(hits, key=lambda x: x.get("lang") or ""):
                if r["status"] == "pass":
                    parts.append("P")
                elif r["status"] == "fail":
                    parts.append(f"{r['score10']}")
                elif r["status"] == "error":
                    parts.append("E")
                else:
                    parts.append("M")
            cells.append("/".join(parts))
        print(f"| {item} | {_level(item)} | " + " | ".join(cells) + " |")

    bad = [r for r in rows if r["status"] in ("error", "missing")]
    if bad:
        print("\n## 异常明细\n")
        for r in sorted(bad, key=lambda x: (x["channel"], x["item"])):
            print(f"- {r['channel']} {r['item']} {r.get('lang') or ''}: {r['status']} {r.get('reason_code')} {r.get('detail') or ''}")
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        merged_rows = sorted(rows, key=lambda x: (x.get("channel", ""), x.get("item", ""), x.get("lang") or ""))
        (args.out / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in merged_rows), encoding="utf-8")
        summary = {ch: bucket([r for r in rows if r["channel"] == ch], args.pass_k) for ch in channels}
        (args.out / "summary.json").write_text(json.dumps({"summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.out / "summary.md").write_text(_render(rows, args.pass_k), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
