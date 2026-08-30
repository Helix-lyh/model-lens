from pathlib import Path

raw = Path("payload.txt").read_text(encoding="utf-8")
lines = raw.split("\n")
hits = []


def check(cond, name) -> None:
    hits.append(1 if cond else 0)
    if not cond:
        print("MISS", name)


check("orchard" not in raw, "no-forward")
check(len(lines) == 5, "five-lines")
check(len(lines) > 0 and lines[0] == "<<HEAD>>", "head")
check(len(lines) > 1 and lines[1] == "drahcro", "rev")
check(len(lines) > 2 and lines[2] == "7", "count")
check(len(lines) > 3 and lines[3] == "dra*cro", "star")
check(len(lines) > 4 and lines[4] == "<<TAIL>>", "tail")
print(f"POINTS {sum(hits)}/{len(hits)}")
