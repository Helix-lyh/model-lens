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
check(isinstance(data, list) and len(data) == 6, "len-6")
if not isinstance(data, list):
    data = [None] * 6
for i, item in enumerate(data[:6]):
    if i == 3:
        check(item is None, "null-3")
        continue
    check(isinstance(item, dict) and set(item) == {"i", "sq", "mark"}, f"keys-{i}")
    check(isinstance(item, dict) and item.get("i") == i and item.get("sq") == i * i, f"vals-{i}")
    if i == 5:
        check(isinstance(item, dict) and item.get("mark") == "N", "mark-N")
    else:
        check(isinstance(item, dict) and item.get("mark") == "n", f"mark-n-{i}")
print(f"POINTS {sum(hits)}/{len(hits)}")
