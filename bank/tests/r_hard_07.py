from _structured import emit, exact_keys, strict_int

KEYS = {"n", "left", "right"}


def _counts(d: dict) -> bool:
    return (
        strict_int(d.get("n"))
        and strict_int(d.get("left"))
        and strict_int(d.get("right"))
        and d["n"] == 10
        and d["left"] + d["right"] == 10
    )


def _strategy(d: dict) -> bool:
    # 9 只右手套已覆盖三色（任意两色最多 8），再加 1 左即保证同色一对。
    return _counts(d) and d["left"] == 1 and d["right"] == 9


emit(
    [
        ("keys", lambda d: exact_keys(d, KEYS)),
        ("n", _counts),
        ("strategy", _strategy),
    ]
)
