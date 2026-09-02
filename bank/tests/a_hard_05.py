from _structured import emit, exact_keys

KEYS = {"atomic_write", "publisher_retry", "consumer_key", "ack_order", "dead_letter", "replay"}
emit([
    ("keys", lambda d: exact_keys(d, KEYS)),
    ("atomic", lambda d: d.get("atomic_write") == "ONE_DB_TRANSACTION"),
    ("publisher", lambda d: d.get("publisher_retry") == "RETRY_UNSENT"),
    ("consumer", lambda d: d.get("consumer_key") == "event_id"),
    ("ack", lambda d: d.get("ack_order") == "COMMIT_THEN_ACK"),
    ("dead", lambda d: d.get("dead_letter") == "AFTER_MAX_RETRIES"),
    ("replay", lambda d: d.get("replay") == "IDEMPOTENT"),
])
