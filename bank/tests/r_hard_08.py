from _structured import emit, exact_keys, strict_int

KEYS = {"n", "smooth", "rough"}


def _counts(d: dict) -> bool:
    return (
        strict_int(d.get("n"))
        and strict_int(d.get("smooth"))
        and strict_int(d.get("rough"))
        and d["n"] == 12
        and d["smooth"] + d["rough"] == 12
    )


def _strategy(d: dict) -> bool:
    # 12 只粗糙：必有蓝（R+G 最多 7）也必有绿（R+B 最多 11）。
    return _counts(d) and d["smooth"] == 0 and d["rough"] == 12


emit(
    [
        ("keys", lambda d: exact_keys(d, KEYS)),
        ("n", _counts),
        ("strategy", _strategy),
    ]
)
