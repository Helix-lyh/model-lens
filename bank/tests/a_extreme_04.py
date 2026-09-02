from _structured import emit, exact_keys, close

KEYS = {"relation", "resolution", "value", "vector", "audit"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("relation", lambda d: d.get("relation") == "CONCURRENT"),
    ("resolution", lambda d: d.get("resolution") == "MANUAL_MERGE"),
    ("value", lambda d: d.get("value") == "A+B"),
    ("vector", lambda d: d.get("vector") == {"east": 5, "west": 4}),
    ("audit", lambda d: d.get("audit") == "RETAIN_BOTH"),
])
