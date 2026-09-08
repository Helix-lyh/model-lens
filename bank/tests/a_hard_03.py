from _structured import emit, exact_keys, strict_bool, strict_int

KEYS = {"redis_owner", "a_renew", "a_write", "b_write", "brain_split", "required_guard"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("redis", lambda d: d.get("redis_owner") == "B"),
    ("renew", lambda d: d.get("a_renew") == "REJECT"),
    ("a-write", lambda d: d.get("a_write") == "REJECT_FENCING"),
    ("b-write", lambda d: d.get("b_write") == "ACCEPT"),
    ("split", lambda d: strict_bool(d.get("brain_split")) and d["brain_split"] is False),
    ("guard", lambda d: d.get("required_guard") == "COMPARE_AND_SET_TOKEN"),
])
