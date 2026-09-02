from _structured import emit, exact_keys

KEYS = {"trace", "final", "rolled_back", "replayed"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("trace", lambda d: d.get("trace") == [5, 10, 13, 10, 13]),
    ("final", lambda d: type(d.get("final")) is int and d["final"] == 13),
    ("rolled", lambda d: d.get("rolled_back") == "ADD_3"),
    ("replayed", lambda d: d.get("replayed") == "ADD_3"),
])
