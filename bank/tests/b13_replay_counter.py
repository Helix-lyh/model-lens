from solution import replay_counter


def hit(log, expect, name) -> int:
    try:
        ok = replay_counter(log) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += hit([], {"balance": 0, "accepted": [], "rejected": []}, "empty")
n += hit([("a", "credit", 10), ("b", "debit", 3)], {"balance": 7, "accepted": ["a", "b"], "rejected": []}, "credit-debit")
n += hit([("a", "credit", 5), ("a", "credit", 9)], {"balance": 5, "accepted": ["a"], "rejected": ["a"]}, "duplicate")
n += hit([("x", "debit", 1)], {"balance": 0, "accepted": [], "rejected": ["x"]}, "insufficient")
n += hit([("a", "credit", 10), ("b", "debit", 6), ("c", "refund", 4)], {"balance": 8, "accepted": ["a", "b", "c"], "rejected": []}, "refund")
n += hit([("a", "credit", 2), ("c", "refund", 1), ("b", "debit", 1), ("c", "refund", 5)], {"balance": 1, "accepted": ["a", "b"], "rejected": ["c", "c"]}, "bad-refund")
n += hit([("a", "credit", 1), ("b", "debit", 1), ("c", "refund", 2)], {"balance": 0, "accepted": ["a", "b"], "rejected": ["c"]}, "refund-too-large")
print(f"POINTS {n}/7")
