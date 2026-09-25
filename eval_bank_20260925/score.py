"""严格 JSON 内容判分与有限轮次汇总；不评价模型的隐藏思考文本。"""

from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
import json
import math
import re

from . import VERSION
from .catalog import BY_ID
from .oracles import REASONING_ORACLES


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


@lru_cache(None)
def golden(item_id):
    return REASONING_ORACLES[item_id]()


def _fraction_equal(got, expected):
    return (
        isinstance(got, list)
        and len(got) == 2
        and all(type(x) is int for x in got)
        and got[1] > 0
        and Fraction(*got) == Fraction(*expected)
    )


def _leaves(got, expected):
    if isinstance(expected, dict):
        obj = got if isinstance(got, dict) else {}
        return [check for k, v in expected.items() for check in _leaves(obj.get(k), v)]
    if isinstance(expected, list):
        if not isinstance(got, list) or len(got) != len(expected):
            return [False] * max(1, len(expected))
        return [strict_equal(a, b) for a, b in zip(got, expected)] or [True]
    return [strict_equal(got, expected)]


def _shape_matches(got, expected):
    """Protocol shape is exact at every object level, independent of values."""
    if isinstance(expected, dict):
        return isinstance(got, dict) and set(got) == set(expected) and all(
            _shape_matches(got[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(got, list) or len(got) != len(expected):
            return False
        return all(_shape_matches(a, b) for a, b in zip(got, expected))
    return type(got) is type(expected)


def reasoning_groups(item_id, data):
    expected = golden(item_id)
    values = {}
    for name, _ in BY_ID[item_id].groups:
        if name in expected:
            values[name] = _leaves(data.get(name), expected[name])
    if item_id == "R-E-01":
        got = data.get("impossible")
        valid = (
            isinstance(got, list)
            and all(type(x) is int for x in got)
            and got == sorted(set(got))
        )
        if valid:
            # 每个正确成员一分；每个多报成员抵消一分；全列 1..50 不能得分。
            earned = max(
                0,
                len(set(got) & set(expected["impossible"]))
                - len(set(got) - set(expected["impossible"])),
            )
            values["impossible"] = [True] * earned + [False] * (10 - earned)
        else:
            values["impossible"] = [False] * 10
        values["largest_count"] = [
            valid
            and strict_equal(got, expected["impossible"])
            and strict_equal(data.get(k), expected[k])
            for k in ("largest", "count")
        ]
    if item_id == "R-E-02":
        values = {k: [_fraction_equal(data.get(k), v)] for k, v in expected.items()}
    if item_id == "R-N-01":
        c = data.get("counterexample")
        valid = isinstance(c, dict) and set(c) == {"left", "right"}
        if valid:
            a, b = c["left"], c["right"]
            valid = (
                isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 3
            )
            if valid:
                valid = all(
                    type(x) is int and 0 <= x <= limit
                    for xs, caps in ((a, [3, 5, 4]), (b, [4, 2, 6]))
                    for x, limit in zip(xs, caps)
                )
                valid = (
                    valid
                    and sum(a) == sum(b) == 5
                    and not any(x and y for x, y in zip(a, b))
                )
        values["counterexample"] = [valid]
        values["allocations"] = [
            strict_equal(data.get("allocations"), expected["allocations"])
        ]
    if item_id == "R-N-02":
        values["count7"] = [
            strict_equal(data.get("parity7"), expected["parity7"])
            and strict_equal(data.get("count7"), expected["count7"])
        ]
    if item_id == "R-H-01":
        # makespan 和 starts 各自得分，起始时间向量必须整体形成最优方案。
        for key in ("base", "changed"):
            block = data.get(key) if isinstance(data.get(key), dict) else {}
            values[key] = [
                strict_equal(block.get("makespan"), expected[key]["makespan"]),
                strict_equal(block.get("starts"), expected[key]["starts"]),
            ]
    if item_id == "R-H-02":
        # value/weight/indices 是同一个方案，必须整组一致；value_ties 独立。
        for key in ("base", "changed"):
            block = data.get(key) if isinstance(data.get(key), dict) else {}
            plan = all(
                strict_equal(block.get(k), expected[key][k])
                for k in ("indices", "value", "weight")
            )
            values[key] = [
                plan,
                plan,
                plan,
                strict_equal(block.get("value_ties"), expected[key]["value_ties"]),
            ]
        values["delta"] = [
            strict_equal(data.get("base"), expected["base"])
            and strict_equal(data.get("changed"), expected["changed"])
            and strict_equal(data.get("delta"), expected["delta"])
        ]
    if item_id == "R-X-01":
        values["adaptive"] = [
            strict_equal(data.get("first_action_costs"), expected["first_action_costs"])
            and strict_equal(data.get("adaptive"), expected["adaptive"])
        ]
    if item_id == "R-X-02":
        values["selected"] = [
            strict_equal(
                data.get("horizontal_histogram"), expected["horizontal_histogram"]
            )
            and strict_equal(data.get("selected"), expected["selected"])
        ]
        values["orbits"] = [
            all(
                strict_equal(data.get(k), expected[k])
                for k in ("selected", "rotation_fixed", "orbits")
            )
        ]
    return values


def score_reasoning(item_id, text):
    item = BY_ID[item_id]
    if item.reference:
        raise ValueError("coding_item")
    try:
        data = parse_json(text)
    except (ValueError, TypeError, RecursionError):
        return Score(
            item_id, None, "fail", "format_error", 0.0, 20, 0.0, False, [], False
        )
    protocol = _shape_matches(data, golden(item_id))
    verdicts = reasoning_groups(item_id, data)
    groups = []
    total = Fraction(0)
    complete = protocol
    for name, budget in item.groups:
        checks = verdicts[name]
        earned = Fraction(budget * sum(checks), len(checks))
        total += earned
        complete = complete and all(checks)
        groups.append(
            {
                "name": name,
                "points": float(earned),
                "max": budget,
                "passed_checks": sum(checks),
                "checks": len(checks),
            }
        )
    return Score(
        item_id,
        None,
        "pass" if complete else "fail",
        "ok" if complete else "content_mismatch" if protocol else "schema_mismatch",
        float(total),
        20,
        round(float(total) / 2, 4),
        complete,
        groups,
        protocol,
    )


def summarize_repair(rounds):
    """r 从 1 开始；使用完整一轮的内容分，不跨轮拼接检查项。"""
    if not 1 <= len(rounds) <= 3:
        raise ValueError("round_count_must_be_1_to_3")
    identity = {(r.version, r.item_id, r.language) for r in rounds}
    if len(identity) != 1:
        raise ValueError("round_identity_mismatch")
    for r in rounds:
        if r.status not in {"pass", "fail", "missing", "error"} or r.points_total != 20:
            raise ValueError("invalid_round")
        if r.status in {"pass", "fail"}:
            if (
                type(r.points) not in (float, int)
                or not math.isfinite(r.points)
                or not 0 <= r.points <= 20
            ):
                raise ValueError("invalid_points")
            if (
                r.passed != (r.status == "pass")
                or r.passed
                and (r.points != 20 or not r.protocol_ok)
            ):
                raise ValueError("inconsistent_pass")
        elif r.points is not None or r.passed is not None:
            raise ValueError("missing_or_error_must_be_null")
    first_solved = next((i for i, r in enumerate(rounds, 1) if r.passed), None)
    if first_solved is not None and first_solved < len(rounds):
        raise ValueError("rounds_after_first_pass")
    # 保留历史 missing 语义；基础设施故障也不能伪装成第 N 轮模型修复。
    if any(r.status in {"missing", "error"} for r in rounds):
        return {
            "version": rounds[0].version,
            "item_id": rounds[0].item_id,
            "language": rounds[0].language,
            "status": "incomplete",
            "rounds_observed": len(rounds),
            "pass1": rounds[0].passed,
            "score10_first": rounds[0].score10,
            "solve_within_k": None,
            "rounds_to_solve": None,
            "discounted_score10": None,
            "selected_round": None,
            "repair_credit10": None,
            "reason_codes": [
                r.reason_code for r in rounds if r.status in {"missing", "error"}
            ],
        }
    factors = [1.0, 0.7, 0.45]
    weighted = [r.points / 2 * factors[i] for i, r in enumerate(rounds)]
    best = max(range(len(rounds)), key=lambda i: weighted[i])
    return {
        "version": VERSION,
        "item_id": rounds[0].item_id,
        "language": rounds[0].language,
        "status": "complete",
        "rounds_observed": len(rounds),
        "pass1": rounds[0].passed,
        "score10_first": rounds[0].score10,
        "solve_within_k": first_solved is not None,
        "rounds_to_solve": first_solved,
        "discounted_score10": round(weighted[best], 4),
        "selected_round": best + 1,
        "repair_credit10": (
            None if first_solved is None else 10 * factors[first_solved - 1]
        ),
    }
