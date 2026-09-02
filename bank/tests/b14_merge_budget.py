from solution import merge_budget


def hit(intervals, budget, expect, name) -> int:
    try:
        ok = merge_budget(intervals, budget) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += hit([], 0, {"ok": True, "intervals": [], "reason": "empty"}, "empty")
n += hit([(1, 3), (3, 5)], 5, {"ok": True, "intervals": [(1, 5)], "reason": "empty"}, "adjacent")
n += hit([(5, 7), (1, 2), (2, 4)], 7, {"ok": True, "intervals": [(1, 7)], "reason": "empty"}, "sort-overlap")
n += hit([(1, 3), (10, 10)], 3, {"ok": False, "intervals": [], "reason": "budget_exceeded"}, "budget")
n += hit([(3, 2)], 10, {"ok": False, "intervals": [], "reason": "invalid"}, "invalid")
n += hit([(0, 0), (-2, -1)], 3, {"ok": True, "intervals": [(-2, 0)], "reason": "empty"}, "negative")
print(f"POINTS {n}/6")
