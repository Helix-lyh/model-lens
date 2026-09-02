from _structured import emit, exact_keys, strict_int

KEYS = {"order", "slot_A", "slot_D", "feasible"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("order", lambda d: d.get("order") == ["A", "C", "B", "D"]),
    ("a", lambda d: strict_int(d.get("slot_A")) and d["slot_A"] == 1),
    ("d", lambda d: strict_int(d.get("slot_D")) and d["slot_D"] == 4),
    ("feasible", lambda d: type(d.get("feasible")) is bool and d["feasible"] is True),
])
