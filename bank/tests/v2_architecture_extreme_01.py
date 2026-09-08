from _structured import emit, exact_keys
from pathlib import Path
import json

EXPECTED = {'actions': ['APPLY', 'FUNDS', 'DUP', 'APPLY', 'APPLY', 'REFUND_LIMIT', 'APPLY'], 'balance': 7, 'refundable_a': 9, 'seen': ['a', 'b', 'c', 'd', 'e', 'f']}
STRICT = False

def equal(value, expected):
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return value.keys() == expected.keys() and all(equal(value[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(value) == len(expected) and all(equal(a, b) for a, b in zip(value, expected))
    return value == expected

def protocol(d):
    return not STRICT or Path("payload.txt").read_text() == json.dumps(EXPECTED, ensure_ascii=False, separators=(",", ":"))

emit([("schema", lambda d: exact_keys(d, set(EXPECTED))), ("protocol", protocol)] +
     [(k, lambda d, k=k: equal(d.get(k), EXPECTED[k])) for k in EXPECTED])
