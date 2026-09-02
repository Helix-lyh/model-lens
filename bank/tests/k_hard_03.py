from _structured import emit, exact_keys, close

KEYS = {"after_discount", "tax_base", "tax", "total"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("discount", lambda d: close(d.get("after_discount"), 770.0)),
    ("base", lambda d: close(d.get("tax_base"), 790.0)),
    ("tax", lambda d: close(d.get("tax"), 63.2)),
    ("total", lambda d: close(d.get("total"), 853.2)),
])
