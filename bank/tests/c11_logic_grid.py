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


def person(key):
    p = obj.get(key)
    return p if isinstance(p, dict) else {}


check(isinstance(data, dict) and list(data.keys()) == ["A", "B", "C"], "top-keys")
check(all(list(person(k).keys()) == ["floor", "drink"] for k in ("A", "B", "C")), "person-keys")
check(person("A").get("floor") == 2, "a-floor")
check(person("A").get("drink") == "茶", "a-drink")
check(person("B").get("floor") == 3, "b-floor")
check(person("B").get("drink") == "咖啡", "b-drink")
check(person("C").get("floor") == 1, "c-floor")
check(person("C").get("drink") == "可乐", "c-drink")
print(f"POINTS {sum(hits)}/{len(hits)}")
