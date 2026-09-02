from _structured import emit, exact_keys

KEYS = {"base_indices", "base_value", "changed_indices", "changed_value", "difference"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("base-indices", lambda d: d.get("base_indices") == [0, 1, 3]),
    ("base-value", lambda d: type(d.get("base_value")) is int and d["base_value"] == 17),
    ("changed-indices", lambda d: d.get("changed_indices") == [0, 1, 3]),
    ("changed-value", lambda d: type(d.get("changed_value")) is int and d["changed_value"] == 17),
    ("difference", lambda d: type(d.get("difference")) is int and d["difference"] == 0),
])
