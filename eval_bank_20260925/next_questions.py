"""20261008 active 30-item descriptors.

The source of truth is the three next-bank documents. Each item is executable
through a small deterministic scorer; domain-specific fixtures can be upgraded
without changing runner or registry interfaces.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from .bank_registry import ITEMS, ItemPlugin

ROOT = Path(__file__).resolve().parents[1]
DOCS = {
    "coding": ROOT / "docs/question-bank-next-coding-20261008.md",
    "engineering": ROOT / "docs/question-bank-next-engineering-20261008.md",
    "reasoning": ROOT / "docs/question-bank-next-reasoning-20261008.md",
}

def _sections(path: Path, prefix: str) -> dict[str, tuple[str,str]]:
    text = path.read_text(encoding="utf-8")
    hits = list(re.finditer(rf"^## ({prefix}-\d{{2}}) (.+)$", text, re.M))
    out = {}
    for i, hit in enumerate(hits):
        body = text[hit.start(): hits[i+1].start() if i+1 < len(hits) else len(text)]
        out[hit.group(1)] = (hit.group(2), body.strip())
    return out

def install_design_descriptors() -> None:
    # Every active 20261008 item must have an executable plugin.  Design
    # documents are prompt provenance, not a fallback scorer.
    for domain, prefix in (("coding","CP"),("engineering","E"),("reasoning","NX")):
        for item_id, (title, body) in _sections(DOCS[domain], prefix).items():
            if item_id not in ITEMS:
                raise RuntimeError(f"active item has no executable plugin: {item_id}")
