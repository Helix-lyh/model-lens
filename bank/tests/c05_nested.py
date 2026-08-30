import json
from pathlib import Path

raw = Path("payload.txt").read_text(encoding="utf-8")
hits = []


def check(cond, name) -> None:
    hits.append(1 if cond else 0)
    if not cond:
        print("MISS", name)


check("/*" not in raw and "//" not in raw, "no-comment")
check(not raw.rstrip().endswith(",}"), "no-trailing-comma")
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = None
check(isinstance(data, dict) and list(data.keys()) == ["root"], "root-only")
cur = data.get("root") if isinstance(data, dict) else None
for key in ("ok", "ok", "ok", "0k", "ok"):
    check(isinstance(cur, dict) and key in cur, f"key:{key}")
    cur = cur[key] if isinstance(cur, dict) else None
check(isinstance(cur, dict) and cur.get("tip") == 42 and type(cur.get("tip")) is int, "tip-42")
check(isinstance(cur, dict) and cur.get("_") == [0, None, False], "underscore-arr")
check(isinstance(cur, dict) and set(cur) == {"tip", "_"}, "inner-keys")
print(f"POINTS {sum(hits)}/{len(hits)}")
