from solution import cook_text


def _hit(s, expect, name) -> int:
    try:
        got = cook_text(s)
        ok = got == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit("", {"vowels": {}, "squeezes": 0, "nums": []}, "empty")
n += _hit("book", {"vowels": {"o": 2}, "squeezes": 1, "nums": []}, "oo")
n += _hit("a12b3", {"vowels": {"a": 1}, "squeezes": 0, "nums": [12, 3]}, "nums")
n += _hit("AAE", {"vowels": {"a": 2, "e": 1}, "squeezes": 1, "nums": []}, "case")
n += _hit("x7y", {"vowels": {}, "squeezes": 0, "nums": [7]}, "digit")
print(f"POINTS {n}/5")
