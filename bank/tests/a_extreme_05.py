from _structured import emit, exact_keys, strict_int

KEYS = {"global_limit", "burst_capacity", "accepted_s1", "accepted_s2", "rejected_policy", "recovery"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("limit", lambda d: strict_int(d.get("global_limit")) and d["global_limit"] == 240),
    ("burst", lambda d: strict_int(d.get("burst_capacity")) and d["burst_capacity"] == 60),
    ("s1", lambda d: strict_int(d.get("accepted_s1")) and d["accepted_s1"] == 300),
    ("s2", lambda d: strict_int(d.get("accepted_s2")) and d["accepted_s2"] == 60),
    ("reject", lambda d: d.get("rejected_policy") == "DROP_NO_REFUND"),
    ("recovery", lambda d: d.get("recovery") == "RETRY_IDEMPOTENT"),
])
