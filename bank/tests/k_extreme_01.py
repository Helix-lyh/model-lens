from _structured import emit, exact_keys, close

KEYS = {"load_kwh", "battery_kwh", "days_supported", "status"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("load", lambda d: close(d.get("load_kwh"), 2.1, tolerance=0.0005)),
    ("battery", lambda d: close(d.get("battery_kwh"), 2.4, tolerance=0.0005)),
    ("days", lambda d: close(d.get("days_supported"), 1.029, tolerance=0.0005)),
    ("status", lambda d: d.get("status") == "ONE_DAY"),
])
