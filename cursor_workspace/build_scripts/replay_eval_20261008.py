#!/usr/bin/env python3
"""Replay saved model responses through the current 20261008 scorers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cursor_workspace.build_scripts.run_eval_20260925 import (  # noqa: E402
    ALL_BY_ID,
    _item_domain,
    _score_item,
    _verdict_fields,
    summarize,
    write_summary,
)
from eval_bank_20260925.bank_manifest import item_provenance  # noqa: E402
from eval_bank_20260925.evaluation import scoring_provenance  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    requests = args.run_dir / "deepseek-flash" / "requests.jsonl"
    if not requests.is_file():
        parser.error(f"missing {requests}")
    rows = []
    for line in requests.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        kind = str(record.get("kind", ""))
        item_id, _, language = kind.partition(":")[-1].partition("-")
        # kind is eval20261008:CP-09-python; split from the right.
        task = kind.split(":", 1)[-1]
        parts = task.split("-")
        if parts[-1] in {"python", "go", "typescript"}:
            language = parts[-1]
            item_id = "-".join(parts[:-1])
        else:
            language = None
            item_id = task
        item = ALL_BY_ID[item_id]
        content = record.get("content") or ""
        verdict = _verdict_fields(_score_item(item, item_id, language, content))
        row = {
            "channel": record.get("channel", "deepseek-flash"),
            "model": record.get("model", "deepseek-flash"),
            "item": item_id,
            "lang": language,
            "sample": 0,
            "run_id": args.out.name,
            "experiment_id": args.out.name,
            **item_provenance(item_id),
            **scoring_provenance(item, language),
            **verdict,
            "response_model": record.get("raw", {}).get("model") if isinstance(record.get("raw"), dict) else None,
            "usage": record.get("usage"),
            "latency_ms": record.get("latency_ms"),
            "replayed_from": str(requests),
        }
        rows.append(row)
    rows.sort(key=lambda row: (row["item"], row.get("lang") or ""))
    args.out.mkdir(parents=True, exist_ok=True)
    meta = {
        "experiment_id": args.out.name,
        "run_id": args.out.name,
        "phase": "hard",
        "bank_profile": "active",
        "bank_version": "20261008",
        "langs": ["python", "go", "typescript"],
        "models": ["deepseek-flash"],
        "samples": 1,
        "pass_k": 1,
        "concurrency": 0,
        "replay": True,
        "source_run": str(args.run_dir),
    }
    # The shared summarizer groups by the historical item shape.  Replay rows
    # use the active registry's explicit domain to keep the three栏 buckets
    # independent and preserve engineering's signed ledger.
    from eval_bank_20260925.evaluation import summarize_engineering, summarize as summarize_generic
    summary = {"deepseek-flash": {}}
    mine = rows
    for domain in ("coding", "engineering", "reasoning"):
        selected = [row for row in mine if _item_domain(row["item"]) == domain]
        summary["deepseek-flash"][domain] = (
            summarize_engineering(selected, pass_k=1)
            if domain == "engineering" else summarize_generic(selected, pass_k=1)
        )
    # write_summary accepts the same shape produced by the live runner.
    (args.out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows),
        encoding="utf-8",
    )
    (args.out / "summary.json").write_text(json.dumps({"meta": meta, "summary": summary, "bank_version": "20261008"}, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "summary.md").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out / "summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
