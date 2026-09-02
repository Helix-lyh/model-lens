from _structured import emit, exact_keys, strict_int

KEYS = {"failure_code", "index_columns", "pagination", "cursor_predicate", "rows_scanned"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("failure", lambda d: d.get("failure_code") == "OFFSET_SCAN"),
    ("index", lambda d: d.get("index_columns") == ["created_at", "id"]),
    ("pagination", lambda d: d.get("pagination") == "KEYSET"),
    ("predicate", lambda d: d.get("cursor_predicate") == "(created_at,id)<(cursor_time,cursor_id)"),
    ("rows", lambda d: strict_int(d.get("rows_scanned")) and d["rows_scanned"] == 20),
])
