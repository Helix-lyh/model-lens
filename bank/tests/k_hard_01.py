from _structured import emit, exact_keys, strict_number, strict_int, close

KEYS = {"reading_mA", "upper_mA", "risk", "unit"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("reading", lambda d: close(d.get("reading_mA"), 2.4)),
    ("upper", lambda d: close(d.get("upper_mA"), 2.52, tolerance=0.005)),
    ("risk", lambda d: d.get("risk") == "HIGH"),
    ("unit", lambda d: d.get("unit") == "mA"),
])
