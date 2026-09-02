from _structured import emit, exact_keys, close

KEYS = {"before_total", "before_decision", "after_total", "after_decision", "delta"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("before-total", lambda d: close(d.get("before_total"), 1029.0)),
    ("before-decision", lambda d: d.get("before_decision") == "REVIEW"),
    ("after-total", lambda d: close(d.get("after_total"), 999.6)),
    ("after-decision", lambda d: d.get("after_decision") == "ACCEPT"),
    ("delta", lambda d: close(d.get("delta"), -29.4)),
])
