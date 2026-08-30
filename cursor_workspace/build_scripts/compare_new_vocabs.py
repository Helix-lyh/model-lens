#!/usr/bin/env python3
"""对新下的官方词表与现有 catalog 做 14 探针 L1。决定合并还是单列。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.catalog import (  # noqa: E402
    HFTokenizerVocab,
    _load_grok_tok,
    _load_hunyuan,
    load_catalog,
)
from src.probes import load_family_probes  # noqa: E402
from tokenizers import Tokenizer  # noqa: E402


def vector(vocab, base, probes) -> list[int]:
    return [vocab.n_hat(base, p.text, escaped=p.escaped) for p in probes]


def l1(a: list[int], b: list[int]) -> int:
    return sum(abs(x - y) for x, y in zip(a, b, strict=True))


def main() -> int:
    catalog = load_catalog(ROOT)
    base, probes = load_family_probes(ROOT)
    vectors = {vid: vector(v, base, probes) for vid, v in catalog.items()}

    extras: dict[str, object] = {}
    dsv4 = ROOT / "catalog/tokenizers/deepseek_v4.json"
    mimo = ROOT / "catalog/tokenizers/mimo.json"
    hy = ROOT / "catalog/tokenizers/hunyuan.tiktoken"
    grok = ROOT / "catalog/tokenizers/grok2.tok.json"
    if dsv4.is_file():
        extras["deepseek_v4"] = HFTokenizerVocab("deepseek_v4", Tokenizer.from_file(str(dsv4)))
    if mimo.is_file():
        extras["mimo"] = HFTokenizerVocab("mimo", Tokenizer.from_file(str(mimo)))
    if hy.is_file():
        extras["hunyuan"] = _load_hunyuan({"id": "hunyuan"}, hy)
    if grok.is_file():
        extras["grok2"] = _load_grok_tok({"id": "grok2"}, grok)

    extra_vecs = {vid: vector(v, base, probes) for vid, v in extras.items()}

    print("=== new vs existing (L1 / exact_hits) ===")
    for nid, nv in extra_vecs.items():
        print(f"\n{nid} n_hat={nv}")
        ranked = []
        for oid, ov in vectors.items():
            ranked.append((l1(nv, ov), sum(a == b for a, b in zip(nv, ov, strict=True)), oid))
        ranked.sort()
        for dist, hits, oid in ranked:
            mark = " COLLAPSE" if dist == 0 else ""
            print(f"  vs {oid:16} L1={dist:4} hits={hits}/{len(probes)}{mark}")

    print("\n=== new vs new ===")
    ids = list(extra_vecs)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            dist = l1(extra_vecs[a], extra_vecs[b])
            print(f"  {a} vs {b}: L1={dist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
