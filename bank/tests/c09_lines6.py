from pathlib import Path

raw = Path("payload.txt").read_text(encoding="utf-8")
lines = raw.split("\n")
hits = []


def check(cond, name) -> None:
    hits.append(1 if cond else 0)
    if not cond:
        print("MISS", name)


check("signal" not in raw, "no-forward")
check(len(lines) == 6, "six-lines")
check(len(lines) > 0 and lines[0] == "[[v2]]", "head")
check(len(lines) > 1 and lines[1] == "sgnl", "no-vowel")
check(len(lines) > 2 and lines[2] == "sgnl-sgnl", "dup")
check(len(lines) > 3 and lines[3] == "9", "count")
check(len(lines) > 4 and lines[4] == "lngs", "rev")
check(len(lines) > 5 and lines[5] == "[[end]]", "tail")
print(f"POINTS {sum(hits)}/{len(hits)}")
