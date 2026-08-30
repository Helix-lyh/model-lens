from solution import pack_runs


def _hit(xs, expect, name) -> int:
    try:
        ok = pack_runs(xs) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit([], [], "empty")
n += _hit([7], [(7, 1)], "single")
n += _hit([1, 1, 1, 2, 2], [(1, 3), (2, 2)], "two-runs")
n += _hit([3, 1, 1, 3], [(3, 1), (1, 2), (3, 1)], "split")
n += _hit([0, 0, 0, 0], [(0, 4)], "zeros")
print(f"POINTS {n}/5")
