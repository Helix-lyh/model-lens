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
n += hit([(5, 10), (1, 10)], 5, {"value": 10, "weight": 5, "indices": [0]}, "lex-before-weight")

# Deterministic exhaustive cases: generated independently from the solution.
def oracle(items, capacity):
    best = (0, 0, [])
    for mask in range(1 << len(items)):
        chosen = [i for i in range(len(items)) if mask & (1 << i)]
        weight = sum(items[i][0] for i in chosen)
        value = sum(items[i][1] for i in chosen)
        if weight <= capacity and (value > best[0] or (value == best[0] and chosen < best[2])):
            best = (value, weight, chosen)
    return {"value": best[0], "weight": best[1], "indices": best[2]}

for seed in range(12):
    items = [((seed * 7 + i * 3) % 6 + 1, (seed * 11 + i * 5) % 13 - 3) for i in range(5)]
    cap = (seed * 5) % 13
    n += hit(items, cap, oracle(items, cap), f"generated-{seed}")
print(f"POINTS {n}/19")
