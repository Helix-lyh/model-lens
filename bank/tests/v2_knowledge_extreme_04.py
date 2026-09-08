from _structured import emit, exact_keys
from pathlib import Path
import json

EXPECTED = {'encodings': ['MY======', 'MZXQ====', 'MZXW6==='], 'alphabet_last': '7', 'bits_per_symbol': 5}
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
