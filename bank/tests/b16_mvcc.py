from solution import apply_transactions


def hit(initial, txns, expect, name) -> int:
    try:
        ok = apply_transactions(initial, txns) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += hit({}, [], {"state": {}, "statuses": {}}, "empty")
n += hit({"a": 0}, [{"id": "t1", "begin": 0, "writes": {"a": 2}, "commit": 1}], {"state": {"a": 2}, "statuses": {"t1": "COMMIT"}}, "one")
n += hit(
    {"a": 0},
    [
        {"id": "t1", "begin": 0, "writes": {"a": 2}, "commit": 2},
        {"id": "t2", "begin": 0, "writes": {"a": 3}, "commit": 1},
    ],
    {"state": {"a": 3}, "statuses": {"t1": "ABORT", "t2": "COMMIT"}},
    "commit-order",
)
n += hit(
    {"a": 0},
    [
        {"id": "t1", "begin": 0, "writes": {"a": 2}, "commit": 1},
        {"id": "t2", "begin": 0, "writes": {"a": 3}, "commit": 2},
    ],
    {"state": {"a": 2}, "statuses": {"t1": "COMMIT", "t2": "ABORT"}},
    "conflict",
)
n += hit(
    {"a": 0, "b": 0},
    [
        {"id": "x", "begin": 0, "writes": {"a": 1}, "commit": 1},
        {"id": "y", "begin": 0, "writes": {"b": 2}, "commit": 2},
    ],
    {"state": {"a": 1, "b": 2}, "statuses": {"x": "COMMIT", "y": "COMMIT"}},
    "disjoint",
)
n += hit(
    {"a": 1},
    [
        {"id": "late", "begin": 1, "writes": {"a": 9}, "commit": 20},
        {"id": "early", "begin": 0, "writes": {"a": 4}, "commit": 10},
    ],
    {"state": {"a": 9}, "statuses": {"late": "COMMIT", "early": "COMMIT"}},
    "begin-version",
)
print(f"POINTS {n}/6")
