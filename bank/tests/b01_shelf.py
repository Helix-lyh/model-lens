from solution import apply_ops


def _hit(ops, expect, name) -> int:
    try:
        got = apply_ops(ops)
        ok = got == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit([], {"A": 0, "B": 0, "C": 0}, "empty")
n += _hit(["+ A 3"], {"A": 3, "B": 0, "C": 0}, "add")
n += _hit(["+ A 2", "- A 5"], {"A": 2, "B": 0, "C": 0}, "underflow-ignore")
n += _hit(["+ A 4", "> A B"], {"A": 0, "B": 4, "C": 0}, "move")
n += _hit(["+ C 1", "? C"], {"A": 1, "B": 0, "C": 0}, "rotate-c")
n += _hit(["+ B 2", "? B", "? B"], {"A": 0, "B": 0, "C": 2}, "rotate-b-twice")
print(f"POINTS {n}/6")
