"""严格 JSON 内容判分与有限轮次汇总；不评价模型的隐藏思考文本。"""

from dataclasses import asdict, dataclass
import json
import math
import re

from . import VERSION


def strict_equal(got, expected):
    if type(got) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(got) == set(expected) and all(
            strict_equal(got[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return len(got) == len(expected) and all(
            strict_equal(a, b) for a, b in zip(got, expected)
        )
    return got == expected


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite_number")


def _float(text):
    number = float(text)
    if not math.isfinite(number):
        raise ValueError("nonfinite_number")
    return number


def parse_json(text):
    if not isinstance(text, str):
        raise ValueError("response_not_text")
    # Providers may prepend a UTF-8 BOM when serializing a JSON response.
    stripped = text.lstrip("\ufeff").strip()
    fence = re.fullmatch(
        r"```json\s*\n(.*?)\n?```", stripped, re.DOTALL | re.IGNORECASE
    )
    if fence:
        stripped = fence.group(1)
    obj = json.loads(
        stripped, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float
    )
    if not isinstance(obj, dict):
        raise ValueError("expected_object")
    return obj


@dataclass
class Score:
    item_id: str
    language: str | None
    status: str
    reason_code: str
    points: float | None
    points_total: int
    score10: float | None
    passed: bool | None
    groups: list[dict]
    protocol_ok: bool
    version: str = VERSION

    def to_dict(self):
        return asdict(self)
