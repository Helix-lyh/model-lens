from solution import tag_scores


def _hit(items, expect, name) -> int:
    try:
        ok = tag_scores(items) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit([], {}, "empty")
n += _hit(["a:1", "b:2", "a:3"], {"a": 4, "b": 2}, "sum")
n += _hit(["a:-3", "a:5"], {"a": 2}, "negative")
n += _hit(["x", ":5", "a:one", "a:1:2"], {}, "invalid")
n += _hit(["cpu:10", "bad", "cpu:-4", "mem:7", ":9"], {"cpu": 6, "mem": 7}, "mixed")
print(f"POINTS {n}/5")
