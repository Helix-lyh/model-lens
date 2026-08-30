from __future__ import annotations

from src.probes import load_family_probes


def test_base_nonempty() -> None:
    base, _probes = load_family_probes()
    assert base
    assert base != ""
    assert base == "The quick brown fox.\n"


def test_fourteen_probes_two_escaped() -> None:
    _base, probes = load_family_probes()
    assert len(probes) == 14
    escaped = [p for p in probes if p.escaped]
    assert len(escaped) == 2
    texts = {p.text for p in escaped}
    assert texts == {"[gMASK]", "<|im_start|>"}
    plain = [p for p in probes if not p.escaped]
    assert len(plain) == 12


def test_required_probe_shapes() -> None:
    _base, probes = load_family_probes()
    by_id = {p.id: p for p in probes}
    assert set(by_id) >= {
        "digit64",
        "pi80",
        "han",
        "kana",
        "hangul",
        "thai",
        "arabic",
        "emoji",
        "glue",
        "mixed",
        "python",
        "special_ws",
        "gmask",
        "im_start",
    }
    assert by_id["digit64"].text == "7" * 64
    assert "\u200b" in by_id["special_ws"].text
    assert "\u00a0" in by_id["special_ws"].text
    assert "👨‍👩‍👧‍👦" in by_id["emoji"].text
    assert by_id["gmask"].escaped is True
    assert by_id["im_start"].escaped is True
