import json
from pathlib import Path

raw = Path("payload.txt").read_text(encoding="utf-8")
hits = []


def check(cond, name) -> None:
    hits.append(1 if cond else 0)
    if not cond:
        print("MISS", name)


try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = None
obj = data if isinstance(data, dict) else {}
arr = obj.get("data") if isinstance(obj.get("data"), list) else []
meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
check(isinstance(data, dict) and list(data.keys()) == ["data", "meta"], "top-keys")
check(len(arr) == 4, "len-4")
check(len(arr) > 0 and isinstance(arr[0], str) and arr[0] == "0", "str-zero")
check(len(arr) > 1 and type(arr[1]) is int and arr[1] == 0, "int-zero")
check(len(arr) > 2 and arr[2] is False, "false")
check(len(arr) > 3 and arr[3] is None, "null")
check(list(meta.keys()) == ["v", "k k"] and meta.get("k k") == {}, "meta-keys")
check("1e2" in raw and meta.get("v") == 100, "sci-notation")
print(f"POINTS {sum(hits)}/{len(hits)}")
