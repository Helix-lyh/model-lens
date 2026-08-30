from __future__ import annotations

import warnings

import pytest

from src.catalog import available_ids, load_catalog, load_model_family_map, lookup_claimed_family
from src.probes import load_family_probes


def test_tiktoken_always_loadable() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        catalog = load_catalog()
    assert "cl100k_base" in catalog
    assert "o200k_base" in catalog
    assert catalog["cl100k_base"].encode_len("hello") > 0
    assert catalog["o200k_base"].encode_len("hello") > 0
    ids = available_ids(catalog)
    assert "cl100k_base" in ids
    assert "o200k_base" in ids


def test_n_hat_is_delta_not_raw_encode() -> None:
    catalog = load_catalog()
    vocab = catalog["cl100k_base"]
    base, probes = load_family_probes()
    assert base
    probe = probes[0]
    expected = vocab.encode_len(base + probe.text, escaped=probe.escaped) - vocab.encode_len(
        base, escaped=probe.escaped
    )
    assert vocab.n_hat(base, probe.text, escaped=probe.escaped) == expected
    # BPE 不是加法：n_hat 禁止退化成 encode(probe)
    merge_base, merge_probe = "foo", "bar"
    delta = vocab.n_hat(merge_base, merge_probe)
    assert delta == vocab.encode_len(merge_base + merge_probe) - vocab.encode_len(merge_base)
    assert delta != vocab.encode_len(merge_probe)


def test_model_family_map_covers_required() -> None:
    m = load_model_family_map()
    assert m["glm-4"] == "glm4"
    assert m["glm-4.5"] == "glm4"
    assert m["glm-5"] == "glm5"
    assert m["glm-5.3-flash"] == "glm5"
    assert m["qwen2.5"] == "qwen2_5"
    assert m["qwen3"] == "qwen2_5"
    assert m["qwen3.8"] == "qwen3_8"
    assert m["deepseek-v3"] == "deepseek_v3"
    assert m["deepseek-chat"] == "deepseek_v3"
    assert m["deepseek-v4"] == "deepseek_v3"
    assert m["deepseek-v4-flash"] == "deepseek_v3"
    assert lookup_claimed_family("deepseek-v4-pro", m) == "deepseek_v3"
    assert m["kimi"] == "kimi"
    assert m["moonshot-v1"] == "kimi"
    assert m["gpt-4o"] == "o200k_base"
    assert m["gpt-4-turbo"] == "cl100k_base"
    assert m["gpt-3.5"] == "cl100k_base"
    assert m["minimax"] == "minimax"
    assert m["MiniMax-M1"] == "minimax"
    assert m["qwen3"] != "qwen3_8"
    assert m["mimo"] == "qwen2_5"
    assert m["mimo-v2-flash"] == "qwen2_5"
    assert lookup_claimed_family("MiMo-V2-Flash", m) == "qwen2_5"
    assert m["hunyuan"] == "hunyuan"
    assert m["hunyuan-turbo"] == "hunyuan"
    assert lookup_claimed_family("hunyuan-a13b-instruct", m) == "hunyuan"
    assert m["grok-2"] == "grok2"
    assert m["grok-2-mini"] == "grok2"
    assert lookup_claimed_family("grok-2-1212", m) == "grok2"
    assert lookup_claimed_family("grok-4.5", m) is None
    assert lookup_claimed_family("grok-4.6", m) is None
    assert lookup_claimed_family("MiniMax-M1-80k", m) == "minimax"


def test_glm4_ne_glm5_if_present() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        catalog = load_catalog()
    if "glm4" not in catalog or "glm5" not in catalog:
        pytest.skip("glm tokenizer files not present")
    base, probes = load_family_probes()
    by_id = {p.id: p for p in probes}
    differ = False
    for pid in ("digit64", "thai", "emoji"):
        p = by_id[pid]
        n4 = catalog["glm4"].n_hat(base, p.text, escaped=p.escaped)
        n5 = catalog["glm5"].n_hat(base, p.text, escaped=p.escaped)
        if n4 != n5:
            differ = True
    assert differ, "glm4 and glm5 collapsed on digit64/thai/emoji"


def test_qwen2_5_ne_qwen3_8_if_present() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        catalog = load_catalog()
    if "qwen2_5" not in catalog or "qwen3_8" not in catalog:
        pytest.skip("qwen tokenizer files not present")
    base, probes = load_family_probes()
    by_id = {p.id: p for p in probes}
    differ = False
    for pid in ("digit64", "thai", "emoji"):
        p = by_id[pid]
        n_a = catalog["qwen2_5"].n_hat(base, p.text, escaped=p.escaped)
        n_b = catalog["qwen3_8"].n_hat(base, p.text, escaped=p.escaped)
        if n_a != n_b:
            differ = True
    assert differ, "qwen2_5 and qwen3_8 collapsed on digit64/thai/emoji"


def _has_added_token(vocab, token_str: str) -> bool:
    tok = getattr(vocab, "_tok", None)
    if tok is None:
        return False
    added = tok.get_added_tokens_decoder()
    for added_tok in added.values():
        content = getattr(added_tok, "content", None) or str(added_tok)
        if content == token_str:
            return True
    return False


def _assert_not_collapsed(catalog: dict, vid: str, *, min_l1: int = 1) -> None:
    if vid not in catalog:
        pytest.skip(f"{vid} tokenizer file not present")
    base, probes = load_family_probes()
    mine = [catalog[vid].n_hat(base, p.text, escaped=p.escaped) for p in probes]
    assert any(n > 0 for n in mine)
    for other_id, vocab in catalog.items():
        if other_id == vid:
            continue
        other = [vocab.n_hat(base, p.text, escaped=p.escaped) for p in probes]
        l1 = sum(abs(a - b) for a, b in zip(mine, other, strict=True))
        assert l1 >= min_l1, f"{vid} collapsed with {other_id}: L1={l1}"


def test_minimax_optional_does_not_collapse_if_present() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        catalog = load_catalog()
    _assert_not_collapsed(catalog, "minimax", min_l1=14)


def test_hunyuan_does_not_collapse_if_present() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        catalog = load_catalog()
    _assert_not_collapsed(catalog, "hunyuan")


def test_grok2_optional_does_not_collapse_if_present() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        catalog = load_catalog()
    _assert_not_collapsed(catalog, "grok2")
    if "hunyuan" in catalog and "grok2" in catalog:
        base, probes = load_family_probes()
        a = [catalog["hunyuan"].n_hat(base, p.text, escaped=p.escaped) for p in probes]
        b = [catalog["grok2"].n_hat(base, p.text, escaped=p.escaped) for p in probes]
        assert a != b, "hunyuan and grok2 share pretok but must not share n_hat"


def test_glm_gmask_escaped_differs_if_present() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        catalog = load_catalog()
    glm = catalog.get("glm5") or catalog.get("glm4")
    if glm is None:
        pytest.skip("glm tokenizer file not present")
    if not _has_added_token(glm, "[gMASK]"):
        pytest.skip("[gMASK] is not an added token on this glm vocab")
    base, _probes = load_family_probes()
    n_esc = glm.n_hat(base, "[gMASK]", escaped=True)
    n_raw = glm.n_hat(base, "[gMASK]", escaped=False)
    assert n_esc != n_raw
