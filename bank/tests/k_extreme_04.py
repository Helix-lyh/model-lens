from _structured import emit, exact_keys, strict_int

KEYS = {"winning_rule", "decision", "suppressed_rules", "evidence_count"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("winner", lambda d: d.get("winning_rule") == "R3"),
    ("decision", lambda d: d.get("decision") == "REVIEW"),
    ("suppressed", lambda d: d.get("suppressed_rules") == ["R2", "R1"]),
    ("evidence", lambda d: strict_int(d.get("evidence_count")) and d["evidence_count"] == 1),
])
