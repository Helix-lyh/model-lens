import json
from pathlib import Path

raw = Path("payload.txt").read_text(encoding="utf-8")
hits = []


def check(cond, name) -> None:
    hits.append(1 if cond else 0)
    if not cond:
        print("MISS", name)


check("\n" not in raw and "\r" not in raw, "one-line")
check("-0" in raw, "minus-zero")
check(raw.count(" ") <= 3, "spaces")
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = None
check(isinstance(data, dict) and list(data.keys()) == ["z", "a", "z2"], "key-order")
check(isinstance(data, dict) and data.get("z") == {"z": {"z": "ok"}}, "z-nest")
check(isinstance(data, dict) and data.get("a") == [], "a-empty")
check(isinstance(data, dict) and data.get("z2") == 0, "z2-zero")
print(f"POINTS {sum(hits)}/{len(hits)}")
