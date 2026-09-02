from _structured import emit, exact_keys, strict_int

KEYS = {"counterexample", "square", "divisible_by_4", "verdict"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("counterexample", lambda d: strict_int(d.get("counterexample")) and d["counterexample"] == 2),
    ("square", lambda d: strict_int(d.get("square")) and d["square"] == 4),
    ("divisible", lambda d: type(d.get("divisible_by_4")) is bool and d["divisible_by_4"] is False),
    ("verdict", lambda d: d.get("verdict") == "FALSE"),
])
