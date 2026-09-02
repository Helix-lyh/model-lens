from _structured import emit, exact_keys, strict_int

KEYS = {"labels", "red_count", "green_count"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("labels", lambda d: d.get("labels") == ["AMBER", "GREEN", "RED", "GREEN"]),
    ("red", lambda d: strict_int(d.get("red_count")) and d["red_count"] == 1),
    ("green", lambda d: strict_int(d.get("green_count")) and d["green_count"] == 2),
])
