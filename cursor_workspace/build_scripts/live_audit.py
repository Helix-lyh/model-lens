#!/usr/bin/env python3
"""实网 audit --quick：可加长超时。密钥只读环境变量。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.bank import load_questions, run_bank
from src.catalog import load_catalog, lookup_claimed_family
from src.client import ChatClient, JsonlRecorder
from src.compare import decide_degrade, decide_identity
from src.config import load_targets
from src.family import format_family_line, run_family
from src.probes import load_family_probes
from src.report import write_run_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--quick", action="store_true")
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
    print(format_family_line(family), flush=True)
    bank = run_bank(
        client,
        load_questions(ROOT),
        salt=run_dir.name,
        quick=args.quick,
        repo=ROOT,
        kind_prefix="bank",
    )
    for domain, row in bank.domain_pass0.items():
        print(f"bank {domain}={row['passed']}/{row['judged']}", flush=True)
    identity = decide_identity(
        family,
        targets,
        claimed_family=lookup_claimed_family(targets.claimed_model),
        bank=bank,
    )
    degrade = decide_degrade(
        identity,
        family,
        targets,
        bank,
        None,
        quick=args.quick,
        force=False,
    )
    print(f"I={identity.status}", flush=True)
    print(f"D={degrade.status}", flush=True)
    write_run_report(
        run_dir,
        targets=targets,
        family=family,
        bank=bank,
        identity=identity,
        degrade=degrade,
    )
    print(run_dir, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
