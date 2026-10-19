#!/usr/bin/env python3
"""跑入选题库：编码 10 + 工程 10 + 现行推理 10 + 20261008 原推理 10。

原推理用独立题号 NX08-09..NX08-18，避免盖住现行 NX-09..NX-18。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import eval_bank_20260925.plugins  # noqa: E402  先装活跃 30 题
from eval_bank_20260925 import bank_manifest as manifest  # noqa: E402
from eval_bank_20260925 import next_reasoning_20261008 as orig  # noqa: E402
from eval_bank_20260925.bank_registry import ITEMS, ItemPlugin  # noqa: E402
from eval_bank_20260925.bank_manifest import BankSpec  # noqa: E402


ORIG_BANK = BankSpec(
    "legacy-reasoning-20261008",
    "20261008 原推理副本",
    "20261008",
    "active",
    "cursor_workspace/build_scripts/run_eval_selected_groups.py",
    "eval_bank_20260925.evaluation.score_item",
    "NX08-09 到 NX08-18，不进 ACTIVE_ITEMS。",
    tuple(f"NX08-{n:02d}" for n in range(9, 19)),
    adapter_id="reasoning",
)


def install_orig() -> None:
    if ORIG_BANK.id not in manifest.BANKS_BY_ID:
        manifest.BANKS_BY_ID[ORIG_BANK.id] = ORIG_BANK
    for spec in orig.ITEMS:
        oid = "NX08-" + spec.item_id.split("-", 1)[1]
        ITEMS.register(ItemPlugin(
            oid,
            "reasoning",
            "[20261008] " + spec.title,
            lambda language=None, iid=spec.item_id: orig.render_reasoning_prompt(iid),
            lambda text, language=None, iid=spec.item_id: orig.score_reasoning(iid, text),
        ), replace=True)
        manifest.BANKS_BY_ITEM[oid] = ORIG_BANK

CODING = [f"CP-{n:02d}" for n in range(9, 19)]
ENGINEERING = [f"E-{n:02d}" for n in range(1, 11)]
REASONING_NOW = [f"NX-{n:02d}" for n in range(9, 19)]
REASONING_ORIG = [f"NX08-{n:02d}" for n in range(9, 19)]
SELECTED = CODING + ENGINEERING + REASONING_NOW + REASONING_ORIG


def main() -> int:
    install_orig()
    argv = sys.argv[1:]
    if not any(a == "--phase" or a.startswith("--phase=") for a in argv):
        argv = ["--phase", "hard", *argv]
    if not any(a == "--langs" or a.startswith("--langs=") for a in argv):
        argv = ["--langs", "python,go,typescript", *argv]
    if not any(a == "--models" or a.startswith("--models=") for a in argv):
        argv = ["--models", "deepseek-flash", *argv]
    if not any(a == "--items" or a.startswith("--items=") for a in argv):
        argv = ["--items", ",".join(SELECTED), *argv]
    if not any(a == "--concurrency" or a.startswith("--concurrency=") for a in argv):
        argv = ["--concurrency", "8", *argv]
    sys.argv = [sys.argv[0], *argv]

    from cursor_workspace.build_scripts.run_eval_20260925 import ALL_BY_ID, EngineeringItem, main as run

    for plugin in ITEMS.items():
        if plugin.item_id not in ALL_BY_ID:
            ALL_BY_ID[plugin.item_id] = EngineeringItem(
                plugin.item_id, "extreme", plugin.title, plugin.prompt(), kind=plugin.domain,
            )
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
