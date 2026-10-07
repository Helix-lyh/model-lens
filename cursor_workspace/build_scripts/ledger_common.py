"""台账页与横向对比页共用的常量、取数与格式化。

两个页面同源，避免各写一套口径。这里只放不会因为页面而变的东西：
题面目录、业务分组、百分制与原始分的格式化、得分点条。
"""

from __future__ import annotations

import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_bank_20260925.next_questions import DOCS, _sections  # noqa: E402

LEDGER = 20
MINUS = "−"
SUITE = "寸衡"

DOMAINS = (
    ("access", "账号权限"),
    ("money", "资金结算"),
    ("stock", "库存供给"),
    ("fulfill", "履约配送"),
    ("schedule", "调度排程"),
    ("care", "就诊安排"),
    ("release", "配置发布"),
    ("record", "单据处理"),
    ("trip", "出行安排"),
)
DOMAIN_OF = {
    "CP-09": "money", "CP-10": "fulfill", "CP-11": "release", "CP-12": "access",
    "CP-13": "money", "CP-14": "stock", "CP-15": "access", "CP-16": "release",
    "CP-17": "record", "CP-18": "trip",
    "E-01": "access", "E-02": "money", "E-03": "stock", "E-04": "record",
    "E-05": "schedule", "E-06": "release", "E-07": "stock", "E-08": "money",
    "E-09": "schedule", "E-10": "record",
    "NX-09": "care", "NX-10": "schedule", "NX-11": "stock", "NX-12": "fulfill",
    "NX-13": "trip", "NX-14": "schedule", "NX-15": "care", "NX-16": "stock",
    "NX-17": "trip", "NX-18": "fulfill",
}
DOMAIN_TOTAL = LEDGER * 10


def latest_run(phase: str = "hard") -> Path:
    runs = sorted(
        path for path in (ROOT / "out").glob(f"eval-20261008-*-{phase}")
        if (path / "results.jsonl").is_file() and (path / "meta.json").is_file()
    )
    if not runs:
        raise SystemExit(f"没有 20261008 的 {phase} 成绩")
    return runs[-1]


def load_run(run_dir: Path) -> tuple[dict, list[dict]]:
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return meta, rows


def pct(points: int | float, total: int) -> str:
    value = (Decimal(str(points)) * 100 / Decimal(total)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return format(value, "f").replace("-", MINUS)


def qpct(points: int | float, total: int) -> str:
    value = Decimal(str(points)) * 100 / Decimal(total)
    step = Decimal(1) if value == value.to_integral() else Decimal("0.1")
    return format(value.quantize(step, rounding=ROUND_HALF_UP), "f").replace("-", MINUS)


def signed(value: int | float) -> str:
    number = int(value) if float(value).is_integer() else value
    return f"{MINUS}{-number}" if float(value) < 0 else str(number)


def num(value: int | float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def pips(count: int, lit: int, cls: str = "on", void: bool = False) -> str:
    out = []
    for index in range(count):
        if void:
            out.append('<i class="void"></i>')
        elif index < lit:
            out.append(f'<i class="{cls}" style="--i:{index}"></i>')
        else:
            out.append("<i></i>")
    return f'<span class="pips" aria-hidden="true">{"".join(out)}</span>'


def seconds(row: dict) -> str:
    latency = row.get("latency_ms")
    if not isinstance(latency, (int, float)):
        return ""
    return f" · {round(latency / 1000)} 秒"


_ANCHOR_HEAD = re.compile(r"^(?:编码|工程|推理)[；;]\s*")
_ANCHOR_TAIL = re.compile(r"(?:[；;]|。)\s*(?:本题)?主能力为[^；;。]*。?$")


def _anchor(body: str) -> str:
    """题目简介：取业务锚点行，去掉内部记账用的栏目名和主能力标签。"""
    match = re.search(r"\*\*(?:栏目 / )?业务锚点[^*]*\*\*\s*(.+)", body)
    if not match:
        return ""
    return _ANCHOR_TAIL.sub("", _ANCHOR_HEAD.sub("", match.group(1).strip())).strip()


def catalog() -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    faces: dict[str, tuple[str, str]] = {}
    briefs: dict[str, str] = {}
    for kind, prefix in (("coding", "CP"), ("engineering", "E"), ("reasoning", "NX")):
        for item_id, (title, body) in _sections(DOCS[kind], prefix).items():
            title = re.sub(r"（.*?）", "", title).strip()
            faces[item_id] = (DOMAIN_OF[item_id], title)
            briefs[item_id] = _anchor(body) or title
    return faces, briefs


def css() -> str:
    return (ROOT / "web" / "ledger.css").read_text(encoding="utf-8")
