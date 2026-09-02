from _structured import emit, exact_keys, strict_int

KEYS = {"chosen_source", "chosen_value", "discarded"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("source", lambda d: d.get("chosen_source") == "lab"),
    ("value", lambda d: strict_int(d.get("chosen_value")) and d["chosen_value"] == 18),
    ("discarded", lambda d: d.get("discarded") == ["R2", "R3"]),
])
