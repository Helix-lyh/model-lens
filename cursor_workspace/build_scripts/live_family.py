#!/usr/bin/env python3
"""实网 family：可加长超时。密钥只读环境变量。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.catalog import load_catalog, lookup_claimed_family
from src.client import ChatClient, JsonlRecorder
from src.compare import decide_identity
from src.config import load_targets
from src.family import format_family_line, run_family
from src.probes import load_family_probes
from src.report import write_run_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    targets = load_targets(args.target)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out) / f"run-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    client = ChatClient(
        targets.target,
        JsonlRecorder(run_dir / "requests.jsonl"),
        timeout_s=args.timeout,
        http_client=httpx.Client(timeout=args.timeout),
    )
    catalog = load_catalog(ROOT)
    base, probes = load_family_probes(ROOT)
    family = run_family(client, catalog, base, probes)
    identity = decide_identity(
        family, targets, claimed_family=lookup_claimed_family(targets.claimed_model)
    )
    write_run_report(run_dir, targets=targets, family=family, identity=identity)
    print(format_family_line(family))
    print(f"I={identity.status}")
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
