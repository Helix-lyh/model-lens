from _structured import emit, exact_keys, strict_int

KEYS = {"path", "cost", "hops", "unique"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("path", lambda d: d.get("path") == ["A", "C", "E", "D"]),
    ("cost", lambda d: strict_int(d.get("cost")) and d["cost"] == 7),
    ("hops", lambda d: strict_int(d.get("hops")) and d["hops"] == 3),
    ("unique", lambda d: type(d.get("unique")) is bool and d["unique"] is True),
])
