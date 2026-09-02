from _structured import emit, exact_keys, strict_int

KEYS = {"assignment", "loads", "minimum_resources", "feasible"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("assignment", lambda d: d.get("assignment") == {"A": 1, "B": 1, "C": 2, "D": 2}),
    ("loads", lambda d: d.get("loads") == {"1": 7, "2": 7}),
    ("minimum", lambda d: strict_int(d.get("minimum_resources")) and d["minimum_resources"] == 2),
    ("feasible", lambda d: type(d.get("feasible")) is bool and d["feasible"] is True),
])
