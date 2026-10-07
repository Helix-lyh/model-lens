#!/usr/bin/env python3
"""活跃题库统一执行器，版本 20261008。

编码、工程、推理走同一个请求循环和 eval_bank_20260925.evaluation.score_item。
编程题按题目绑定一种语言。当前主测是 CP-09 到 CP-18：4 道 Python、3 道 Go、3 道 TypeScript。报告里的阶段分和最终得分是百分数。

  .venv/bin/python cursor_workspace/build_scripts/run_eval.py
  .venv/bin/python cursor_workspace/build_scripts/run_eval.py --phase quick --models deepseek-flash
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    argv = sys.argv[1:]
    if not any(arg == "--phase" or arg.startswith("--phase=") for arg in argv):
        argv = ["--phase", "hard", *argv]
    if not any(arg == "--langs" or arg.startswith("--langs=") for arg in argv):
        argv = ["--langs", "python,go,typescript", *argv]
    if not any(arg == "--bank-profile" or arg.startswith("--bank-profile=") for arg in argv):
        argv = ["--bank-profile", "active", *argv]
    sys.argv = [sys.argv[0], *argv]
    from cursor_workspace.build_scripts.run_eval_20260925 import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
