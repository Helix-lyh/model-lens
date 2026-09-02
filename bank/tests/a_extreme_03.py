from _structured import emit, exact_keys, strict_int

KEYS = {"a_result", "b_result", "stored_token", "stored_version", "lease_rule"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("a", lambda d: d.get("a_result") == "REJECT_STALE"),
    ("b", lambda d: d.get("b_result") == "ACCEPT"),
    ("token", lambda d: strict_int(d.get("stored_token")) and d["stored_token"] == 12),
    ("version", lambda d: strict_int(d.get("stored_version")) and d["stored_version"] == 5),
    ("rule", lambda d: d.get("lease_rule") == "TOKEN_CHECK_AT_STORAGE"),
])
