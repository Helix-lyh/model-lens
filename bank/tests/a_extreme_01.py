from _structured import emit, exact_keys, strict_int

KEYS = {"actions", "balance", "accepted_seq", "flags"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("actions", lambda d: d.get("actions") == ["APPLY", "APPLY", "REJECT_DUP", "APPLY", "FLAG"]),
    ("balance", lambda d: strict_int(d.get("balance")) and d["balance"] == 120),
    ("accepted", lambda d: d.get("accepted_seq") == [1, 2, 3]),
    ("flags", lambda d: strict_int(d.get("flags")) and d["flags"] == 1),
])
