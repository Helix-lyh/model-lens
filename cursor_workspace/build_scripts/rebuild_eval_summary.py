#!/usr/bin/env python3
"""Rebuild a run's summaries from its immutable results.jsonl without model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cursor_workspace.build_scripts.run_eval_20260925 import summarize, write_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--pass-at", type=int, default=None)
    args = parser.parse_args()
    results_path = args.run_dir / "results.jsonl"
    meta_path = args.run_dir / "meta.json"
    if not results_path.is_file() or not meta_path.is_file():
        parser.error("run_dir must contain meta.json and results.jsonl")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    names = list(meta.get("models") or dict.fromkeys(row.get("channel") for row in rows if row.get("channel")))
    pass_k = args.pass_at or int(meta.get("pass_k", 1))
    if pass_k < 1 or pass_k > int(meta.get("samples", 1)):
        parser.error("--pass-at must be within the run's recorded sample count")
    meta["pass_k"] = pass_k
    write_summary(args.run_dir, summarize(rows, names, pass_k), rows, meta)
    print(args.run_dir / "summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
