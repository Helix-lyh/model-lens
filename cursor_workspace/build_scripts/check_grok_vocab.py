#!/usr/bin/env python3
"""用 Grok-2 官方 tokenizer.tok.json / 社区 HF 词表，对照一场已落盘的家族差分。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tiktoken
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.catalog import HFTokenizerVocab, TiktokenVocab
from src.probes import load_family_probes

# vLLM grok2.py：word_split == V1 时的 pretok（官方 tok.json 不带 pat_str）
GROK2_PAT = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}|"
    r" ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
)


def load_grok2_tok(path: Path) -> TiktokenVocab:
    data = json.loads(path.read_text(encoding="utf-8"))
    ranks = {bytes(item["bytes"]): int(item["token"]) for item in data.get("regular_tokens") or []}
    special = {
        bytes(item["bytes"]).decode("utf-8", errors="replace"): int(item["token"])
        for item in data.get("special_tokens") or []
    }
    enc = tiktoken.Encoding(
        name="grok2",
        pat_str=data.get("pat_str") or GROK2_PAT,
        mergeable_ranks=ranks,
        special_tokens=special,
        explicit_n_vocab=data.get("vocab_size"),
    )
    return TiktokenVocab("grok2", enc)


def score(vocab, base: str, probes, deltas: dict[str, int]) -> tuple[int, int]:
    hits = 0
    l1 = 0
    for probe in probes:
        api = deltas[probe.id]
        nh = vocab.n_hat(base, probe.text, escaped=probe.escaped)
        if nh == api:
            hits += 1
        l1 += abs(nh - api)
    return hits, l1


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_grok_vocab.py <family.json> [tok.json] [tokenizer.json]")
        return 2
    family = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    deltas = {
        p["probe_id"]: p["delta_api"]
        for p in family["family"]["probes"]
        if not p.get("dropped") and isinstance(p.get("delta_api"), int)
    }
    base, probes = load_family_probes(ROOT)
    used = [p for p in probes if p.id in deltas]
    print(f"probes used={len(used)} model={family.get('claimed')}")

    tok_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/grok-tok/grok2.tok.json")
    hf_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("/tmp/grok-tok/grok2.hf.json")

    if tok_path.is_file():
        vocab = load_grok2_tok(tok_path)
        hits, l1 = score(vocab, base, used, deltas)
        print(f"grok2 tok.json  hits={hits}/{len(used)} l1={l1}")
        for probe in used:
            nh = vocab.n_hat(base, probe.text, escaped=probe.escaped)
            print(f"  {probe.id:16} api={deltas[probe.id]:3} n_hat={nh:3}")
    else:
        print(f"missing {tok_path}")

    if hf_path.is_file():
        vocab = HFTokenizerVocab("grok2_hf", Tokenizer.from_file(str(hf_path)))
        hits, l1 = score(vocab, base, used, deltas)
        print(f"grok2 hf json   hits={hits}/{len(used)} l1={l1}")
    else:
        print(f"missing {hf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
