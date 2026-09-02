from _structured import emit, exact_keys, close

KEYS = {"before", "after", "before_reason", "after_reason"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("before", lambda d: d.get("before") == "B"),
    ("after", lambda d: d.get("after") == "NONE"),
    ("before-reason", lambda d: d.get("before_reason") == "B_MEETS_RULE"),
    ("after-reason", lambda d: d.get("after_reason") == "NO_QUALIFIED_SUPPLIER"),
])
