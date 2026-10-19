from __future__ import annotations

import importlib


def oracle_for(family_id: str):
    return importlib.import_module(f"eval_bank_20260925.worldkit.oracles.{family_id}")
