from solution import SlidingLimiter


def _hit(limit, window, seq, expect, name) -> int:
    try:
        lim = SlidingLimiter(limit, window)
        ok = [bool(lim.allow(ts)) for ts in seq] == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit(2, 10, [1, 2, 3], [True, True, False], "basic")
n += _hit(2, 10, [1, 2, 11, 12, 12], [True, True, True, True, False], "slide")
n += _hit(1, 5, [0, 4, 5], [True, False, True], "boundary")
n += _hit(1, 3, [1, 2, 3, 5], [True, False, False, True], "denied-not-counted")
n += _hit(2, 1, [7, 7, 7], [True, True, False], "same-ts")
n += _hit(3, 4, [1, 2, 3, 4, 6], [True, True, True, False, True], "limit3")
print(f"POINTS {n}/6")
