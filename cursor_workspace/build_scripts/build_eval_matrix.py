"""多模型横向对比页。

同一场 run 里的多个渠道并排：栏级总览 + 逐题矩阵。
并排的前提是可比，所以生成前先过闸门：题库版本、判定脚本、题集、采样口径
必须一致；不一致就拒绝生成，不把不可比的数据放到同一页。

    .venv/bin/python cursor_workspace/build_scripts/build_eval_matrix.py
    .venv/bin/python cursor_workspace/build_scripts/build_eval_matrix.py --run out/eval-...-hard
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cursor_workspace.build_scripts.ledger_common import (  # noqa: E402
    DOMAINS, LEDGER, MINUS, SUITE, catalog, css, latest_run, pct, qpct, signed,
)

SUITE_OUT = ROOT / "docs"

ITEM_FACE, BRIEFS = catalog()
CSS = css()

# 顺序固定：横向对比里三栏不该因为某个模型的分数而换位。
SECTIONS = (
    ("reasoning", "推理", "NX", "每题 20 分 · 百分制"),
    ("coding", "编码", "CP", "每题 20 分 · 百分制"),
    ("engineering", "工程", "E", "每题 20 条关系 · 净分 = 得分点 − 扣分点"),
)


class NotComparable(SystemExit):
    """并排前提不成立。"""


UNJUDGED = frozenset({"missing", "error", "pending_review"})


def _judged(row: dict) -> bool:
    return row.get("status") not in UNJUDGED and row.get("points") is not None


def _points(row: dict, domain: str) -> int | None:
    if not _judged(row):
        return None
    if domain == "engineering":
        if row.get("net_points") is None or row.get("positive_points") is None or row.get("negative_points") is None:
            return None
        return int(row["net_points"])
    return int(row["points"])


def _positive(row: dict, domain: str) -> int:
    return int(row.get("positive_points") or 0) if domain == "engineering" else int(row["points"] or 0)


def _negative(row: dict, domain: str) -> int:
    return int(row.get("negative_points") or 0) if domain == "engineering" else 0


def check_comparable(meta: dict, rows: list[dict]) -> list[str]:
    """可比性闸门。不通过就抛错，不生成页面。"""
    channels = sorted({row["channel"] for row in rows})
    if len(channels) < 2:
        raise NotComparable(f"只有 {len(channels)} 个渠道，横向对比至少需要 2 个")
    if sorted(meta.get("models") or []) != channels:
        raise NotComparable(f"meta.models={meta.get('models')} 与 results 里的渠道 {channels} 不一致")

    by_item: dict[str, list[dict]] = {}
    for row in rows:
        by_item.setdefault(row["item"], []).append(row)

    for item, group in by_item.items():
        got = sorted(row["channel"] for row in group)
        if got != channels:
            raise NotComparable(f"{item} 的渠道不齐：{got}，期望 {channels}")
        scorers = {row.get("scorer_sha256") for row in group}
        if len(scorers) != 1 or not all(isinstance(item_hash, str) and item_hash for item_hash in scorers):
            raise NotComparable(f"{item} 在不同渠道上用的是不同判定脚本：{sorted(map(str, scorers))}")
        versions = {row.get("bank_version") for row in group}
        if len(versions) != 1:
            raise NotComparable(f"{item} 在不同渠道上的题库版本不同：{sorted(map(str, versions))}")
        prompts = {row.get("base_prompt_sha256") for row in group}
        if len(prompts) != 1 or not all(isinstance(item_hash, str) and item_hash for item_hash in prompts):
            raise NotComparable(f"{item} 在不同渠道上的题面不同：{sorted(map(str, prompts))}")
        langs = {row.get("lang") for row in group}
        if len(langs) != 1:
            raise NotComparable(f"{item} 在不同渠道上的语言不同：{sorted(map(str, langs))}")

    expected = set(meta.get("items") or [])
    if expected and expected != set(by_item):
        raise NotComparable(f"results 的题集与 meta.items 不一致：{sorted(set(by_item) ^ expected)}")
    return channels


def _bar(domain: str, value: int | float, scale: int | float) -> str:
    """得分条。宽度是 value/scale。工程栏 0 在中间，负分向左。"""
    width = abs(Decimal(str(value)) / Decimal(str(scale))) if scale else Decimal(0)
    if domain == "engineering":
        cls = " div is-neg" if value < 0 else " div"
        return f'<span class="mbar{cls}" aria-hidden="true"><i style="--v:{width}"></i></span>'
    return f'<span class="mbar" aria-hidden="true"><i style="--v:{width}"></i></span>'


def _counts(pos: int, neg: int, gap: int, scale: int) -> str:
    """三项都写出数字。分母是这三项之和，空白不算没测到。"""
    def bit(label: str, value: int, debt: bool = False) -> str:
        cls = ' class="is-debt"' if debt else ""
        return f'<span{cls}><em>{label}</em><b>{value}<small>/{scale}</small></b></span>'

    return f'<p class="m-counts">{bit("得分点", pos)}{bit("扣分点", neg, True)}{bit("没测到", gap)}</p>'


def _panel(
    domain: str,
    who: str,
    value: int | float | None,
    scale: int | float,
    raw_lines: list[str],
    *,
    counts: tuple[int, int, int] | None = None,
    top: bool = False,
    exact: bool = False,
) -> str:
    cls = "mcell unjudged" if value is None else ("mcell top" if top else "mcell")
    neg = " neg" if value is not None and float(value) < 0 else ""
    if value is None:
        percent = MINUS
    else:
        shown = qpct(value, scale) if exact else pct(value, int(scale))
        percent = f'{shown}<i class="unit"> / 100</i>'
    parts = [
        f'<span class="m-who">{escape(who)}</span>',
        f'<span class="m-pct{neg}">{percent}</span>',
    ]
    if value is not None:
        parts.append(_bar(domain, value, scale))
    raw = "".join(f'<span class="m-raw">{line}</span>' for line in raw_lines)
    parts.append(f'<div class="m-raws">{raw}</div>')
    if counts is not None:
        parts.append(_counts(*counts, counts[0] + counts[1] + counts[2]))
    return f'<td class="{cls}">{"".join(parts)}</td>'


def _cell(row: dict, domain: str, best: int | None, who: str) -> str:
    got = _points(row, domain)
    if got is None:
        reason = str(row.get("reason_code") or "未判")
        return _panel(domain, who, None, LEDGER, [escape(reason)], exact=True)
    counts = None
    if domain == "engineering":
        pos, neg = _positive(row, domain), _negative(row, domain)
        counts = (pos, neg, LEDGER - pos - neg)
    return _panel(
        domain, who, got, LEDGER, [f"原始分 {signed(got)} / {LEDGER} 分"],
        counts=counts, top=best is not None and got == best, exact=True,
    )


def _overview(channels: list[str], rows: list[dict]) -> str:
    head = "".join(f'<th scope="col">{escape(name)}</th>' for name in channels)
    body = []
    for domain, zh, prefix, rule in SECTIONS:
        mine = [row for row in rows if row["item"].startswith(prefix + "-")]
        cells = []
        for name in channels:
            mine_channel = [row for row in mine if row["channel"] == name]
            judged = [row for row in mine_channel if _points(row, domain) is not None]
            if not judged:
                cells.append(_panel(domain, name, None, LEDGER, [f"0 / {len(mine_channel)} 题已判"]))
                continue
            got = [value for row in judged if (value := _points(row, domain)) is not None]
            total, total_max = sum(got), LEDGER * len(got)
            raw = [f"原始分 {signed(total)} / {total_max} 分"]
            if len(judged) != len(mine_channel):
                raw.append(f"{len(judged)} / {len(mine_channel)} 题已判")
            counts = None
            if domain == "engineering":
                pos = sum(_positive(row, domain) for row in judged)
                neg = sum(_negative(row, domain) for row in judged)
                counts = (pos, neg, total_max - pos - neg)
            cells.append(_panel(domain, name, total, total_max, raw, counts=counts))
        body.append(
            f'<tr><th scope="row" class="mq"><b>{zh}</b><span>{len(mine) // len(channels)} 题 · {escape(rule)}</span></th>'
            + "".join(cells)
            + "</tr>"
        )
    return (
        '<section class="mover" id="overview" aria-labelledby="overview-h">'
        '<header class="msec-head"><h2 id="overview-h">三栏总览</h2></header>'
        f'<div class="mscroll"><table class="mtable"><thead><tr><th scope="col" class="mq">栏目</th>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div></section>'
    )


def _domain_blocks(mine: list[dict], channels: list[str], domain: str) -> str:
    out = []
    for key, zh in DOMAINS:
        rows = [row for row in mine if ITEM_FACE[row["item"]][0] == key]
        if not rows:
            continue
        items = sorted({row["item"] for row in rows})
        out.append(f'<tr class="mgrp"><th colspan="{len(channels) + 1}">{zh}<span>{len(items)} 题</span></th></tr>')
        for item in items:
            by_channel = {row["channel"]: row for row in rows if row["item"] == item}
            got = {name: value for name, row in by_channel.items() if (value := _points(row, domain)) is not None}
            best = max(got.values()) if got else None
            title = ITEM_FACE[item][1]
            sample = next(iter(by_channel.values()))
            lang = sample.get("lang") or ""
            lang_bit = f" · {lang}" if lang else ""
            cells = "".join(
                _cell(by_channel[name], domain, best, name) if name in by_channel else f'<td class="mcell missing"><span class="m-who">{escape(name)}</span><span class="m-pct">—</span></td>'
                for name in channels
            )
            out.append(
                f'<tr><th scope="row" class="mq"><h3>{escape(title)}</h3>'
                f'<p class="row-id">{item}{lang_bit}</p>'
                f'<p class="desc"><span class="k">DESC</span>{escape(BRIEFS[item])}</p></th>{cells}</tr>'
            )
    return "".join(out)


def render(meta: dict, rows: list[dict], channels: list[str]) -> str:
    started = str(meta.get("started_at") or "")
    started_date = f"{started[0:4]}-{started[4:6]}-{started[6:8]}" if len(started) >= 8 else ""
    started_hm = f"{started[9:11]}:{started[11:13]}" if len(started) >= 13 else ""
    stamp = f"{started_date} {started_hm}".strip()
    counts = [
        len({row["item"] for row in rows if row["item"].startswith(prefix + "-")})
        for _domain, _zh, prefix, _rule in SECTIONS
    ]
    scope = f"每栏 {counts[0]} 题" if len(set(counts)) == 1 else "题数见各栏"

    heads = "".join(f'<th scope="col">{escape(name)}</th>' for name in channels)
    sections = []
    for index, (domain, zh, prefix, rule) in enumerate(SECTIONS, start=1):
        mine = [row for row in rows if row["item"].startswith(prefix + "-")]
        count = len({row["item"] for row in mine})
        sections.append(
            f'<section class="msec" id="{domain}" aria-labelledby="{domain}-h">'
            f'<header class="msec-head"><p class="sec-index">{index:02d} / {len(SECTIONS):02d}</p>'
            f'<h2 id="{domain}-h">{zh}</h2><p class="sec-sub">本场 {count} 题 · {escape(rule)}</p></header>'
            f'<div class="mscroll"><table class="mtable"><thead><tr><th scope="col" class="mq">题</th>{heads}</tr></thead>'
            f'<tbody>{_domain_blocks(mine, channels, domain)}</tbody></table></div></section>'
        )

    nav = "".join(f'<a href="#{domain}">{zh}</a>' for domain, zh, _prefix, _rule in SECTIONS)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{escape(SUITE)}：{'、'.join(channels)} 同场作答的编码、工程、推理横向对比。">
<title>{escape(SUITE)} · 横向对比 · {escape(started_date)}</title>
<style>
{CSS}</style>
</head>
<body>
<nav class="nav" aria-label="栏">
  <div class="wrap">
    <a class="brand" href="#top"><b>{escape(SUITE)}</b><span>model-lens · {escape(started_date)}</span></a>
    <div class="nav-links">{nav}</div>
  </div>
</nav>
<main id="top">
  <div class="wrap">
    <header class="mhero">
      <h1>{escape(SUITE)}</h1>
      <p class="lede">用私有题库测模型的编码、工程和推理。</p>
      <p class="mhero-meta">{len(channels)} 个模型同场作答 · {scope} · {escape(stamp)}</p>
    </header>
    {_overview(channels, rows)}
    {''.join(sections)}
    <footer class="foot"><p class="colophon">{escape(SUITE)} · model-lens · 题库 {escape(str(meta.get("bank_version") or "—"))} · {escape(stamp)} 这场题面</p></footer>
  </div>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default=None, help="run 目录；默认取最新一场 hard")
    parser.add_argument("--out", default=None, help="输出 HTML 路径")
    args = parser.parse_args()

    run_dir = Path(args.run) if args.run else latest_run()
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    channels = check_comparable(meta, rows)
    started = str(meta.get("started_at") or "")
    out = Path(args.out) if args.out else SUITE_OUT / f"eval-matrix-{started[:8] or 'run'}.html"
    html = render(meta, rows, channels)
    assert "支持" not in html
    out.write_text(html, encoding="utf-8")
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"wrote {shown}  channels={channels}  items={len({r['item'] for r in rows})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
