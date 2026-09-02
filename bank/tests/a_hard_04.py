from _structured import emit, exact_keys, strict_int

KEYS = {"events", "final_state", "ledger_amount", "missing_seq", "idempotent_key"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("events", lambda d: d.get("events") == ["APPLY_SUCCESS", "IGNORE_DUPLICATE", "APPLY_REFUND", "RECONCILE_GAP"]),
    ("state", lambda d: d.get("final_state") == "PARTIALLY_REFUNDED"),
    ("ledger", lambda d: strict_int(d.get("ledger_amount")) and d["ledger_amount"] == 60),
    ("gap", lambda d: d.get("missing_seq") == [5]),
    ("key", lambda d: d.get("idempotent_key") == "payment_id+seq"),
])
