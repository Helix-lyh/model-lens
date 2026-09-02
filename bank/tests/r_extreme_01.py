from _structured import emit, exact_keys

KEYS = {"base_indices", "base_value", "counterfactual_indices", "counterfactual_value", "delta"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("base-indices", lambda d: d.get("base_indices") == [0, 2]),
    ("base-value", lambda d: type(d.get("base_value")) is int and d["base_value"] == 17),
    ("counter-indices", lambda d: d.get("counterfactual_indices") == [0, 2]),
    ("counter-value", lambda d: type(d.get("counterfactual_value")) is int and d["counterfactual_value"] == 17),
    ("delta", lambda d: type(d.get("delta")) is int and d["delta"] == 0),
])
