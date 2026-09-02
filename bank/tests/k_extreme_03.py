from _structured import emit, exact_keys, close, strict_number

KEYS = {"fail_weight", "pass_weight", "decision", "margin"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("fail", lambda d: close(d.get("fail_weight"), 0.9)),
    ("pass", lambda d: close(d.get("pass_weight"), 1.0)),
    ("decision", lambda d: d.get("decision") == "PASS"),
    ("margin", lambda d: close(d.get("margin"), 0.1)),
])
