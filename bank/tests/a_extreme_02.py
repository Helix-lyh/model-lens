from _structured import emit, exact_keys, strict_int

KEYS = {"read_mode", "rollback_mode", "data_action", "compat_window", "lost_records"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("read", lambda d: d.get("read_mode") == "OLD_FIRST"),
    ("rollback", lambda d: d.get("rollback_mode") == "ROLL_BACK_APP_ONLY"),
    ("data", lambda d: d.get("data_action") == "BACKFILL_THEN_RETRY"),
    ("window", lambda d: strict_int(d.get("compat_window")) and d["compat_window"] == 10),
    ("lost", lambda d: strict_int(d.get("lost_records")) and d["lost_records"] == 0),
])
