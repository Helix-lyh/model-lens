from solution import parse_badge


def _hit(raw, expect, name) -> int:
    try:
        ok = parse_badge(raw) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit("24#08.30+2", (2024, 8, 30, 2), "ok")
n += _hit("00#01.01+0", (2000, 1, 1, 0), "y2k")
n += _hit("24#13.01+1", None, "month")
n += _hit("24/08.30+2", None, "sep")
n += _hit("23#02.29+1", None, "leap")
print(f"POINTS {n}/5")
