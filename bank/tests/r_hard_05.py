from _structured import emit, exact_keys

KEYS = {"truth", "liar_count", "consistent"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("truth", lambda d: d.get("truth") == [True, True, False]),
    ("liars", lambda d: type(d.get("liar_count")) is int and d["liar_count"] == 1),
    ("consistent", lambda d: type(d.get("consistent")) is bool and d["consistent"] is True),
])
