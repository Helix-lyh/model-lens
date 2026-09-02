from _structured import emit, exact_keys

KEYS = {"x", "y", "cost", "optimal", "witness"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("x", lambda d: type(d.get("x")) is int and d["x"] == 2),
    ("y", lambda d: type(d.get("y")) is int and d["y"] == 5),
    ("cost", lambda d: type(d.get("cost")) is int and d["cost"] == 3),
    ("optimal", lambda d: type(d.get("optimal")) is bool and d["optimal"] is True),
    ("witness", lambda d: d.get("witness") == "x+y=7"),
])
