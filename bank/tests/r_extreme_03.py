from _structured import emit, exact_keys

KEYS = {"max_confidence", "decision", "value", "witness"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("confidence", lambda d: d.get("max_confidence") == 0.8),
    ("decision", lambda d: d.get("decision") == "CONFLICT"),
    ("value", lambda d: d.get("value") is None),
    ("witness", lambda d: d.get("witness") == ["E1", "E2"]),
])
