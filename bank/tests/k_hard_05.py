from _structured import emit, exact_keys, strict_int

KEYS = {"old_threshold", "new_threshold", "old_action", "new_action"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("old-threshold", lambda d: strict_int(d.get("old_threshold")) and d["old_threshold"] == 11),
    ("new-threshold", lambda d: strict_int(d.get("new_threshold")) and d["new_threshold"] == 15),
    ("old-action", lambda d: d.get("old_action") == "HOLD"),
    ("new-action", lambda d: d.get("new_action") == "RESTOCK"),
])
