from _structured import emit, exact_keys, strict_int, strict_number

KEYS = {"auth", "transport", "parts", "scan", "publish"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("auth", lambda d: d.get("auth") == "SIGNED_URL_900S"),
    ("transport", lambda d: d.get("transport") == "DIRECT_OBJECT_STORAGE"),
    ("parts", lambda d: d.get("parts") == {"size_mib": 16}),
    ("scan", lambda d: d.get("scan") == "QUARANTINED_TO_CLEAN_OR_REJECTED"),
    ("publish", lambda d: d.get("publish") == "CLEAN_ONLY"),
])
