from _structured import emit, exact_keys, strict_bool, strict_int

KEYS = {"swaps", "seven_enough"}
emit(
    [
        ("keys", lambda d: exact_keys(d, KEYS)),
        ("swaps", lambda d: strict_int(d.get("swaps")) and d["swaps"] == 8),
        ("seven", lambda d: strict_bool(d.get("seven_enough")) and d["seven_enough"] is False),
    ]
)
