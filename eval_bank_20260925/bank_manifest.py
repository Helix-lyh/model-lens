"""20261008 活跃题库身份。默认评测只跑这一版。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ACTIVE_VERSION = "20261008"
CODE_LANGS = ("python", "go", "typescript")
# 每道编码题只绑定一种语言：CP-09..CP-12 Python，CP-13..CP-15 Go，CP-16..CP-18 TypeScript。
ITEM_CODE_LANG = {
    "CP-09": "python",
    "CP-10": "python",
    "CP-11": "python",
    "CP-12": "python",
    "CP-13": "go",
    "CP-14": "go",
    "CP-15": "go",
    "CP-16": "typescript",
    "CP-17": "typescript",
    "CP-18": "typescript",
}

PROGRAMMING_ACTIVE = tuple(f"CP-{number:02d}" for number in range(9, 19))
ENGINEERING_ACTIVE = tuple(f"E-{number:02d}" for number in range(1, 11))
REASONING_ACTIVE = tuple(f"NX-{number:02d}" for number in range(9, 19))
QUICK_ACTIVE = ("CP-09", "E-07", "NX-09")
ACTIVE_ITEMS = PROGRAMMING_ACTIVE + ENGINEERING_ACTIVE + REASONING_ACTIVE

# 活跃编码题使用标准库。没有题目绑定第三方 profile。
ITEM_RUNTIME_PROFILES: dict[str, dict[str, str]] = {}
RUNTIME_PROFILE_SPECS: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class BankSpec:
    id: str
    title: str
    version: str
    status: Literal["active"]
    runner: str
    scorer: str
    purpose: str
    item_ids: tuple[str, ...]
    languages: tuple[str, ...] = ()
    adapter_id: str = "coding"


BANKS = (
    BankSpec(
        "business-coding",
        "业务编码题库",
        ACTIVE_VERSION,
        "active",
        "cursor_workspace/build_scripts/run_eval.py",
        "eval_bank_20260925.evaluation.score_item",
        "CP-09 到 CP-18，每题一种语言：4 道 Python、3 道 Go、3 道 TypeScript。",
        PROGRAMMING_ACTIVE,
        CODE_LANGS,
        "coding",
    ),
    BankSpec(
        "business-engineering",
        "业务工程题库",
        ACTIVE_VERSION,
        "active",
        "cursor_workspace/build_scripts/run_eval.py",
        "eval_bank_20260925.evaluation.score_item",
        "许愿式工程行为。正分、负分、净分各自换算成百分数。",
        ENGINEERING_ACTIVE,
        adapter_id="engineering",
    ),
    BankSpec(
        "business-reasoning",
        "业务推理题库",
        ACTIVE_VERSION,
        "active",
        "cursor_workspace/build_scripts/run_eval.py",
        "eval_bank_20260925.evaluation.score_item",
        "NX-09 到 NX-18。",
        REASONING_ACTIVE,
        adapter_id="reasoning",
    ),
)

BANKS_BY_ID = {bank.id: bank for bank in BANKS}
BANKS_BY_ITEM = {item_id: bank for bank in BANKS for item_id in bank.item_ids}
ACTIVE_BANK_IDS = tuple(bank.id for bank in BANKS)
QUICK_BANK_IDS = ACTIVE_BANK_IDS


def bank_for_item(item_id: str) -> BankSpec:
    return BANKS_BY_ITEM[item_id]


def plugin_for_item(item_id: str):
    """Resolve an active item through the pluggable item registry."""
    from .bank_registry import ITEMS

    return ITEMS.resolve(item_id)


def item_provenance(item_id: str) -> dict[str, str]:
    bank = bank_for_item(item_id)
    return {"bank_id": bank.id, "bank_version": bank.version}


def adapter_for_item(item_id: str) -> str:
    return bank_for_item(item_id).adapter_id


def active_item_ids(item_ids: list[str], phase: str) -> list[str]:
    """按调用方给出的顺序保留活跃题。quick 是三题冒烟，hard 是活跃全量。"""
    if phase not in {"quick", "hard"}:
        raise ValueError(f"unknown phase: {phase}")
    allowed = set(QUICK_ACTIVE if phase == "quick" else ACTIVE_ITEMS)
    return [item_id for item_id in item_ids if item_id in allowed]


def bank_status(bank_id: str) -> str:
    return BANKS_BY_ID[bank_id].status
