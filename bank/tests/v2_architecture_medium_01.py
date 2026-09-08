from _structured import emit, exact_keys
from pathlib import Path
import json

EXPECTED = {'phase1_percent': 5, 'metrics': ['error_rate', 'latency', 'http_5xx'], 'window_minutes': 30, 'rollback': {'metric': 'error_rate', 'threshold': 1}}
STRICT = False

def protocol(d):
    return not STRICT or Path("payload.txt").read_text() == json.dumps(EXPECTED, ensure_ascii=False, separators=(",", ":"))

def phase1_percent(d):
    value = d.get('phase1_percent')
    return type(value) is int and 1 <= value <= 20

def metrics(d):
    value = d.get('metrics')
    return (
        type(value) is list
        and len(value) >= 3
        and all(type(item) is str and len(item.strip()) >= 2 for item in value)
        and len(set(value)) == len(value)
    )

def window_minutes(d):
    value = d.get('window_minutes')
    return type(value) is int and value >= 5

def rollback(d):
    value = d.get('rollback')
    chosen = d.get('metrics')
    return (
        type(value) is dict
        and exact_keys(value, {"metric", "threshold"})
        and type(value.get("metric")) is str
        and type(chosen) is list
        and value.get("metric") in chosen
        and type(value.get("threshold")) is int
        and value.get("threshold") >= 1
    )

emit([("schema", lambda d: exact_keys(d, set(EXPECTED))), ("protocol", protocol),
      ("phase1_percent", phase1_percent), ("metrics", metrics),
      ("window_minutes", window_minutes), ("rollback", rollback)])
