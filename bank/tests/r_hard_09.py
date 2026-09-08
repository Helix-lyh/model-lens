from _structured import close, emit, exact_keys, strict_int

KEYS = {"h2022", "h12", "h25", "asl_fail"}
emit(
    [
        ("keys", lambda d: exact_keys(d, KEYS)),
        ("h2022", lambda d: strict_int(d.get("h2022")) and d["h2022"] == 1),
        ("h12", lambda d: strict_int(d.get("h12")) and d["h12"] == 2),
        ("h25", lambda d: strict_int(d.get("h25")) and d["h25"] == 4),
        ("asl", lambda d: close(d.get("asl_fail"), 1.8)),
    ]
)
