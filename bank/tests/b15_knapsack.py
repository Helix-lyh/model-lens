from solution import bounded_knapsack


def hit(items, capacity, expect, name) -> int:
    try:
        ok = bounded_knapsack(items, capacity) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += hit([], 5, {"value": 0, "weight": 0, "indices": []}, "empty")
n += hit([(2, 3)], 1, {"value": 0, "weight": 0, "indices": []}, "none-fit")
n += hit([(4, 7), (5, 9), (6, 10), (3, 5)], 10, {"value": 17, "weight": 10, "indices": [0, 2]}, "global")
n += hit([(2, 5), (2, 5)], 2, {"value": 5, "weight": 2, "indices": [0]}, "tie-lex")
n += hit([(1, -1), (2, 4), (3, 4)], 3, {"value": 4, "weight": 2, "indices": [1]}, "weight-not-objective")
n += hit([(1, 2), (2, 4), (3, 6)], 3, {"value": 6, "weight": 3, "indices": [0, 1]}, "tie-combination")
print(f"POINTS {n}/6")
