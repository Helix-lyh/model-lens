#!/usr/bin/env python3
"""生成并冻结 20261012 推理题实例与答案键（确定性种子 + 参考求解器）。

  .venv/bin/python cursor_workspace/build_scripts/gen_reasoning_20261012.py          # 写入
  .venv/bin/python cursor_workspace/build_scripts/gen_reasoning_20261012.py --check  # 只比对
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.reasoning_gen import build_all  # noqa: E402

OUT = ROOT / "eval_bank_20260925" / "reasoning_20261012.json"


def render() -> str:
    return json.dumps(build_all(), ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render()
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("ok" if same else "DIFF")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
