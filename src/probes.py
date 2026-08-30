"""家族探针加载。"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.types import Probe


def load_family_probes(root: Path | None = None) -> tuple[str, list[Probe]]:
    if root is None:
        root = Path(__file__).resolve().parent.parent
    path = root / "probes" / "family_probes.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = str(data["base"])
    probes = [
        Probe(
            id=str(item["id"]),
            text=str(item["text"]),
            escaped=bool(item.get("escaped", False)),
        )
        for item in data["probes"]
    ]
    return base, probes
