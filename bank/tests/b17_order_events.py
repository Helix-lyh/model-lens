from solution import order_events


def hit(events, expect, name) -> int:
    try:
        ok = order_events(events) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += hit([], {"state": "CREATED", "applied": [], "rejected": []}, "empty")
n += hit([("p", "PAY"), ("s", "SHIP"), ("d", "DELIVER")], {"state": "DELIVERED", "applied": ["p", "s", "d"], "rejected": []}, "happy")
n += hit([("c", "CANCEL"), ("p", "PAY")], {"state": "CANCELLED", "applied": ["c"], "rejected": ["p"]}, "cancel")
n += hit([("p", "PAY"), ("p", "PAY")], {"state": "PAID", "applied": ["p"], "rejected": []}, "duplicate")
n += hit([("s", "SHIP"), ("p", "PAY"), ("r", "REFUND")], {"state": "REFUNDED", "applied": ["p", "r"], "rejected": ["s"]}, "invalid-first")
n += hit([("p", "PAY"), ("r", "REFUND"), ("s", "SHIP")], {"state": "REFUNDED", "applied": ["p", "r"], "rejected": ["s"]}, "refund")
n += hit([("p", "PAY"), ("s", "SHIP"), ("r", "REFUND"), ("d", "DELIVER")], {"state": "REFUNDED", "applied": ["p", "s", "r"], "rejected": ["d"]}, "ship-refund")
print(f"POINTS {n}/7")
