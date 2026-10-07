"""从当前 20261008 跑测生成三栏成绩单。

页面数字来自该次 results.jsonl。三栏分开，不合成跨栏总分。
每题只显示拿到的分，不标严格通过。

    .venv/bin/python cursor_workspace/build_scripts/build_eval_ledger_20261006.py
"""

from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval_bank_20260925.next_questions import DOCS, _sections  # noqa: E402

CHANNEL = "deepseek-flash"
OUT = ROOT / "docs" / "eval-ledger-20261008.html"

from cursor_workspace.build_scripts.ledger_common import (  # noqa: E402
    DOMAINS, LEDGER, MINUS, SUITE, catalog, css, num, pct, pips, qpct, seconds, signed,
)


def _json_lines(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_rows(path: Path) -> list[dict]:
    rows = [row for row in _json_lines(path) if row.get("channel") == CHANNEL]
    return sorted(rows, key=lambda row: row["item"])


def _single_model_run() -> Path:
    """台账页只展示 deepseek-flash。多模型场里这一栏 30 题都已判完，就用最新一场。"""
    found = []
    for path in sorted((ROOT / "out").glob("eval-20261008-*-hard")):
        meta_path, results = path / "meta.json", path / "results.jsonl"
        if not meta_path.is_file() or not results.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("bank_version") != "20261008" or CHANNEL not in (meta.get("models") or []):
            continue
        rows = _json_lines(results)
        mine = [row for row in rows if row.get("channel") == CHANNEL and row.get("status") in {"pass", "fail"}]
        if len(mine) == 30 and len({row["item"] for row in mine}) == 30:
            found.append(path)
    if not found:
        raise SystemExit(f"没有 {CHANNEL} 已判完 30 题的 20261008 hard 成绩")
    return found[-1]


RUN = _single_model_run()
ITEM_FACE, BRIEFS = catalog()
rows = load_rows(RUN / "results.jsonl")
coding = [row for row in rows if row["item"].startswith("CP-")]
engineering = [row for row in rows if row["item"].startswith("E-")]
nx = [row for row in rows if row["item"].startswith("NX-")]
coding_meta = json.loads((RUN / "meta.json").read_text(encoding="utf-8"))

assert coding_meta["bank_version"] == "20261008"
assert CHANNEL in coding_meta["models"]
assert len(coding) == len(engineering) == len(nx) == 10
assert {row["item"] for row in rows} == set(ITEM_FACE)
assert all(row.get("points_total") == LEDGER for row in rows)

def _judged_number(row: dict, *keys: str) -> bool:
    return row.get("status") in {"pass", "fail"} and all(isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool) for key in keys)


coding_judged = [row for row in coding if _judged_number(row, "points")]
engineering_judged = [row for row in engineering if _judged_number(row, "points", "positive_points", "negative_points", "net_points")]
nx_judged = [row for row in nx if _judged_number(row, "points")]
coding_points = sum(row["points"] for row in coding_judged)
coding_total = LEDGER * len(coding_judged)
eng_positive = sum(row["positive_points"] for row in engineering_judged)
eng_negative = sum(row["negative_points"] for row in engineering_judged)
eng_net = sum(row["net_points"] for row in engineering_judged)
eng_total = LEDGER * len(engineering_judged)
eng = {
    "positive_points": eng_positive,
    "negative_points": eng_negative,
    "net_points": eng_net,
}
nx_points = sum(row["points"] for row in nx_judged)
nx_total = LEDGER * len(nx_judged)

request_path = RUN / CHANNEL / "requests.jsonl"
first_request = json.loads(next(line for line in request_path.read_text(encoding="utf-8").splitlines() if line.strip()))
coding_params = first_request["request"]
model_temperature = num(coding_params["temperature"])
model_stream = "流式" if coding_params["stream"] else "非流式"


def group_cell(zh: str, field: str, points: int | float, maximum: int | float) -> str:
    short = float(maximum) - float(points)
    state = "short" if short else "full"
    delta = f'<span class="grp-delta">差 {num(short)}</span>' if short else ""
    return (
        f'<div class="grp grp-{state}" title="{escape(field)} {num(points)}/{num(maximum)}">'
        f'<span class="grp-label"><span class="grp-name">{escape(zh)}</span>{delta}</span>'
        f'<span class="grp-id">{escape(field)}</span>'
        f"{pips(int(maximum), int(points))}</div>"
    )


def score_cell(points: int | float) -> str:
    cls = " neg" if float(points) < 0 else ""
    return (
        f'<div class="row-score"><span class="pct{cls}">{qpct(points, LEDGER)}<i class="unit"> / 100</i></span>'
        f'<span class="pts">原始分 {signed(points)} / {LEDGER} 分</span></div>'
    )


def question_block(item_id: str) -> str:
    return f'<p class="desc"><span class="k">DESC</span>{escape(BRIEFS[item_id])}</p>'


def title_block(row: dict) -> str:
    _domain, title = ITEM_FACE[row["item"]]
    lang = row.get("lang") or ""
    lang_bit = f" · {lang}" if lang else ""
    return (
        f'<div class="row-title"><h3>{escape(title)}</h3>'
        f'<p class="row-id">{row["item"]}{lang_bit}{seconds(row)}</p></div>'
        f"{question_block(row['item'])}"
    )


def coding_row(row: dict) -> str:
    groups = row.get("groups") or []
    cells = "".join(
        group_cell(f"场景 {index}", group["name"], group["points"], group["max"])
        for index, group in enumerate(groups, start=1)
    )
    label = "，".join(f"场景 {index} {num(group['points'])}/{num(group['max'])}" for index, group in enumerate(groups, start=1))
    return (
        f'<li class="row">{title_block(row)}'
        f'<div class="strip" style="--g:{len(groups)}" role="img" aria-label="{escape(label)}">{cells}</div>'
        f"{score_cell(row['points'])}</li>"
    )


def engineering_row(row: dict) -> str:
    cov, hit = int(row["positive_points"]), int(row["negative_points"])
    gap = LEDGER - cov - hit
    return (
        f'<li class="row row-eng">{title_block(row)}'
        f'<div class="ledger" role="img" aria-label="得分点 {cov}/{LEDGER}，扣分点 {hit}/{LEDGER}，没测到 {gap}">'
        f'<div class="lrow"><span class="lk">得分点</span>{pips(LEDGER, cov)}<span class="lv">{cov}<small>/{LEDGER}</small></span></div>'
        f'<div class="lrow lrow-debt"><span class="lk">扣分点</span>{pips(LEDGER, hit, cls="debt")}<span class="lv">{hit}<small>/{LEDGER}</small></span></div>'
        f'<div class="lrow"><span class="lk">没测到</span>{pips(LEDGER, gap, cls="void")}<span class="lv">{gap}<small>/{LEDGER}</small></span></div>'
        f"</div>{score_cell(row['net_points'])}</li>"
    )


def nx_row(row: dict) -> str:
    groups = row.get("groups") or []
    cells = "".join(group_cell(group["name"], group["name"], group["points"], group["max"]) for group in groups)
    label = "，".join(f"{group['name']} {num(group['points'])}/{num(group['max'])}" for group in groups)
    return (
        f'<li class="row">{title_block(row)}'
        f'<div class="strip" style="--g:{max(len(groups), 1)}" role="img" aria-label="{escape(label)}">{cells}</div>'
        f"{score_cell(row['points'])}</li>"
    )


def domain_blocks(rows_in: list[dict], render_row, points_of) -> str:
    blocks = []
    for key, zh in DOMAINS:
        mine = [row for row in rows_in if ITEM_FACE[row["item"]][0] == key]
        if not mine:
            continue
        got = sum(points_of(row) for row in mine)
        shown = signed(got)
        blocks.append(
            f'<li class="mech"><p class="mech-head"><span>{zh}</span>'
            f'<span>{len(mine)} 题 · 原始分 {shown} / {LEDGER * len(mine)} 分</span></p>'
            f'<ol class="rows">{"".join(render_row(row) for row in mine)}</ol></li>'
        )
    return "".join(blocks)


coding_pct = pct(coding_points, coding_total)
eng_pos_pct = pct(eng["positive_points"], eng_total)
eng_neg_pct = pct(eng["negative_points"], eng_total)
eng_net_pct = pct(eng["net_points"], eng_total)
nx_pct = pct(nx_points, nx_total)
eng_net_ratio = Decimal(eng["net_points"]) / Decimal(eng_total)
started = coding_meta["started_at"]
started_date = f"{started[0:4]}-{started[4:6]}-{started[6:8]}"
started_hm = f"{started[9:11]}:{started[11:13]}"

LEGEND_PASS = (
    '<p class="legend" aria-hidden="true">'
    '<span><i class="on"></i>拿到</span><span><i></i>没拿到</span></p>'
)
LEGEND_ENG = (
    '<p class="legend" aria-hidden="true">'
    '<span><i class="on"></i>得分点</span><span><i class="debt"></i>扣分点</span><span><i class="void"></i>没测到</span></p>'
)


def _section(index: int, total: int, sid: str, name: str, score: str, sub: str, legend: str, body: str) -> str:
    return (
        f'<section class="sec" id="{sid}" aria-labelledby="{sid}-h">'
        f'<div class="wrap"><header class="sec-head">'
        f'<p class="sec-index">{index:02d} / {total:02d}</p>'
        f'<div class="sec-title"><h2 id="{sid}-h">{name}</h2><span class="sec-num">{score}<i class="unit"> / 100</i></span></div>'
        f'<p class="sec-sub">{sub}</p></header>'
        f'{legend}<ol class="mechs">{body}</ol></div></section>'
    )


def _book(sid: str, name: str, rule: str, score: str, bar: str, meta: str) -> str:
    return (
        f'<li class="book"><a href="#{sid}"><span class="book-name">{name}</span>'
        f'<span class="book-rule">{rule}</span>'
        f'<span class="book-num">{score}<i class="unit"> / 100</i></span>'
        f'{bar}'
        f'<span class="book-meta">{meta}</span></a></li>'
    )


_columns = [
    {
        "id": "coding",
        "name": "编码",
        "score": Decimal(coding_points) / Decimal(coding_total),
        "book": _book(
            "coding", "编码", f"{len(coding_judged)} 题 · 每题 20 分 · 百分制", coding_pct,
            f'<span class="book-bar" style="--v:{Decimal(coding_points) / coding_total}"><i></i></span>',
            f"原始分 <b>{num(coding_points)}</b> / {coding_total} 分",
        ),
        "legend": LEGEND_PASS,
        "body": domain_blocks(coding, coding_row, lambda row: row["points"]),
        "sub": f"原始分 <b>{num(coding_points)}</b> / {coding_total} 分",
        "pct": coding_pct,
    },
    {
        "id": "engineering",
        "name": "工程",
        "score": Decimal(eng["net_points"]) / Decimal(eng_total),
        "book": _book(
            "engineering", "工程", f"{len(engineering_judged)} 题 · 每题 20 条关系 · 净分 = 得分点 − 扣分点", eng_net_pct,
            f'<span class="book-bar div{" is-neg" if eng_net_ratio < 0 else ""}" style="--v:{abs(eng_net_ratio)}"><i></i><b style="left:0">−100</b><b style="right:0">100</b></span>',
            f"原始分 <b>{signed(eng['net_points'])}</b> / {eng_total} 分",
        ),
        "legend": LEGEND_ENG,
        "body": domain_blocks(engineering, engineering_row, lambda row: row["net_points"]),
        "sub": f"原始分 <b>{signed(eng['net_points'])}</b> / {eng_total} 分 · 得分点 {eng['positive_points']} · 扣分点 {eng['negative_points']}",
        "pct": eng_net_pct,
    },
    {
        "id": "reasoning",
        "name": "推理",
        "score": Decimal(nx_points) / Decimal(nx_total),
        "book": _book(
            "reasoning", "推理", f"{len(nx_judged)} 题 · 每题 20 分 · 百分制", nx_pct,
            f'<span class="book-bar" style="--v:{Decimal(nx_points) / nx_total}"><i></i></span>',
            f"原始分 <b>{num(nx_points)}</b> / {nx_total} 分",
        ),
        "legend": LEGEND_PASS,
        "body": domain_blocks(nx, nx_row, lambda row: row["points"]),
        "sub": f"原始分 <b>{num(nx_points)}</b> / {nx_total} 分",
        "pct": nx_pct,
    },
]
_columns.sort(key=lambda column: column["score"], reverse=True)
nav_books = "".join(f'<a href="#{column["id"]}">{column["name"]}</a>' for column in _columns)
books_html = "".join(column["book"] for column in _columns)
sections_html = "".join(
    _section(index, len(_columns), column["id"], column["name"], column["pct"], column["sub"], column["legend"], column["body"])
    for index, column in enumerate(_columns, start=1)
)


CSS = css()

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#0f120d">
<meta name="description" content="寸衡：{started_date} DeepSeek Flash 的编码、工程、推理成绩。">
<title>寸衡 · DeepSeek Flash · {started_date}</title>
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="preload" href="https://cdn.jsdelivr.net/fontsource/fonts/familjen-grotesk@5.2.8/latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="https://cdn.jsdelivr.net/fontsource/fonts/ibm-plex-mono@5.2.7/latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<script>document.documentElement.classList.add("js")</script>
<style>
{CSS}</style>
</head>
<body>
<header class="nav">
  <div class="wrap">
    <a class="brand" href="#top"><b>{SUITE}</b><span>model-lens · {started_date}</span></a>
    <nav class="nav-links" aria-label="三栏">
      {nav_books}
    </nav>
  </div>
</header>

<main id="top">
  <div class="wrap">
    <div class="hero">
      <div class="hero-copy">
        <div>
          <h1>{SUITE}</h1>
          <p class="lede">用私有题库测模型的编码、工程和推理。</p>
        </div>
        <section class="model" aria-label="被测模型">
          <h2>被测模型</h2>
          <p class="model-name">{escape(str(coding_params["model"]))}</p>
          <p class="model-when">{started_date} {started_hm}</p>
          <ul class="model-pills">
            <li>推理强度 {escape(str(coding_params["reasoning_effort"]))}</li>
            <li>采样温度 {model_temperature}</li>
            <li>传输 {model_stream}</li>
          </ul>
        </section>
      </div>
      <ol class="books">
        {books_html}
      </ol>
    </div>

  </div>

  {sections_html}
</main>

<footer class="foot">
  <div class="wrap">
    <p class="colophon">寸衡 · model-lens · 题库 {escape(coding_meta["bank_version"])} · {started_date} {started_hm} 这场题面</p>
  </div>
</footer>

<script>
(() => {{
  const root = document.documentElement;
  requestAnimationFrame(() => requestAnimationFrame(() => root.classList.add("ready")));
  const links = [...document.querySelectorAll(".nav-links a")];
  const targets = links.map((a) => document.querySelector(a.getAttribute("href"))).filter(Boolean);
  if (!("IntersectionObserver" in window)) {{
    document.querySelectorAll(".row").forEach((row) => row.classList.add("in"));
    return;
  }}
  const spy = new IntersectionObserver((entries) => {{
    entries.forEach((entry) => {{
      if (!entry.isIntersecting) return;
      links.forEach((a) => a.setAttribute("aria-current", String(a.getAttribute("href") === "#" + entry.target.id)));
    }});
  }}, {{ rootMargin: "-35% 0px -55% 0px" }});
  targets.forEach((t) => spy.observe(t));
  const reveal = new IntersectionObserver((entries) => {{
    entries.forEach((entry) => {{
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      reveal.unobserve(entry.target);
    }});
  }}, {{ rootMargin: "0px 0px -8% 0px" }});
  document.querySelectorAll(".row").forEach((row) => reveal.observe(row));
}})();
</script>
</body>
</html>
"""


def main() -> None:
    assert "支持" not in HTML
    OUT.write_text(HTML, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  coding {coding_pct}  engineering {eng_net_pct}  reasoning {nx_pct}")


if __name__ == "__main__":
    main()
