#!/usr/bin/env python3
"""一次性连通性探测：不写密钥，只打印 status / usage / error。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.client import ChatClient, JsonlRecorder
from src.config import load_targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-tokens", type=int, default=None)
    args = parser.parse_args()

    targets = load_targets(args.target)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    client = ChatClient(
        targets.target,
        JsonlRecorder(out / "ping.jsonl"),
        timeout_s=args.timeout,
        max_retries=1,
        http_client=httpx.Client(timeout=args.timeout),
    )
    rec = client.complete(
        [{"role": "user", "content": "The quick brown fox.\n"}],
        temperature=0.0,
        max_tokens=args.max_tokens,
        kind="ping",
    )
    print(
        f"status={rec.status_code} prompt_tokens={rec.prompt_tokens} "
        f"completion_tokens={rec.completion_tokens} error={rec.error}"
    )
    return 0 if rec.status_code and 200 <= rec.status_code < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
