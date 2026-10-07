"""Business facts for CP-09..CP-18.

The scorer does not know these shapes. Each question decides which observed
values count. Equivalent layouts compare equal; wrong amounts and states do not.
"""

from __future__ import annotations


def _as_output(value):
    return value if isinstance(value, dict) else {}


def _rows(value):
    """Only a list is a sequence of observations. A count or other shape is no observation."""
    return value if isinstance(value, list) else []


def _orders(value):
    if isinstance(value, list):
        return {row.get("order") or row.get("id"): row.get("state") for row in value if isinstance(row, dict)}
    if not isinstance(value, dict):
        return {}
    if value and all(isinstance(item, str) for item in value.values()):
        return dict(value)
    found = {}
    for key, body in value.items():
        if isinstance(body, dict):
            for order_id in body:
                found[order_id] = key
        elif isinstance(body, str):
            found[key] = body
    return found


def cp09(output):
    data = _as_output(output)
    return {"quota": data.get("quota"), "orders": _orders(data.get("orders"))}


def cp10(output):
    data = _as_output(output)
    parcels = []
    for row in _rows(data.get("parcels")):
        if not isinstance(row, dict):
            continue
        state = row.get("state")
        batch = row.get("batch")
        if state != "ACCEPTED":
            batch = None
        parcels.append({"parcel": row.get("parcel", row.get("id")), "state": state, "batch": batch})
    batches = [
        {"id": row.get("id"), "used": row.get("used"), "closed": bool(row.get("closed"))}
        for row in _rows(data.get("batches")) if isinstance(row, dict)
    ]
    return {"parcels": parcels, "batches": batches}


def _config_maps(output):
    if isinstance(output, list):
        reads = output
    else:
        reads = _rows(_as_output(output).get("reads"))
    maps = []
    for read in reads:
        if isinstance(read, list):
            maps.append({item.get("key"): item.get("value") for item in read if isinstance(item, dict) and item.get("key") is not None})
        elif isinstance(read, dict) and read.get("key") is not None:
            maps.append({read["key"]: read.get("value")})
    return maps


def cp11(output):
    return {"reads": _config_maps(output)}


def cp12(output):
    data = _as_output(output)
    roots = [row.get("root") for row in _rows(data.get("lookups")) if isinstance(row, dict)]
    edges = []
    for row in _rows(data.get("edges")):
        if isinstance(row, dict):
            edges.append((row.get("tenant"), row.get("from"), row.get("to")))
    return {"roots": roots, "edges": edges}


def _hold_rows(holds):
    if isinstance(holds, dict):
        return [
            {"hold": key, "state": body.get("state"), "remaining": body.get("remaining")}
            for key, body in sorted(holds.items()) if isinstance(body, dict)
        ]
    if isinstance(holds, list):
        return [
            {"hold": body.get("hold"), "state": body.get("state"), "remaining": body.get("remaining")}
            for body in holds if isinstance(body, dict)
        ]
    return []


def cp13(output):
    if isinstance(output, list):
        rows = output
    else:
        data = _as_output(output)
        rows = _rows(data.get("reads"))
        if not rows and "balance" in data:
            rows = [data]
    return [
        {"balance": row.get("balance"), "available": row.get("available"), "holds": _hold_rows(row.get("holds"))}
        for row in rows if isinstance(row, dict) and ("balance" in row or "holds" in row or "available" in row)
    ]


def cp14(output):
    data = _as_output(output)
    reads = []
    for row in _rows(data.get("reads")):
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("batches"), list):
            free = sum((batch.get("free") or 0) for batch in row["batches"] if isinstance(batch, dict))
            locked = sum((batch.get("locked") or 0) for batch in row["batches"] if isinstance(batch, dict))
        else:
            free, locked = row.get("free"), row.get("locked")
        reads.append({"sku": row.get("sku"), "free": free, "locked": locked})
    orders = {row.get("order"): row.get("state") for row in _rows(data.get("orders")) if isinstance(row, dict)}
    return {"reads": reads, "orders": orders}


def _version(value):
    if isinstance(value, dict):
        return value.get("version", value.get("policy"))
    return value


def cp15(output):
    rows = output if isinstance(output, list) else _rows(_as_output(output).get("reads"))
    return [
        {"request": row.get("request"), "state": row.get("state"), "step": row.get("step"), "policy": _version(row.get("policy"))}
        for row in rows if isinstance(row, dict) and "state" in row
    ]


def _walk_tokens(value, found):
    if isinstance(value, dict):
        if "tenant_tokens" in value or "global_tokens" in value:
            found.append({"tenant": value.get("tenant"), "tenant_tokens": value.get("tenant_tokens"), "global_tokens": value.get("global_tokens")})
        for item in value.values():
            _walk_tokens(item, found)
    elif isinstance(value, list):
        for item in value:
            _walk_tokens(item, found)


def cp16(output):
    found = []
    _walk_tokens(output, found)
    return [{"tenant_tokens": row.get("tenant_tokens"), "global_tokens": row.get("global_tokens")} for row in found]


def _miss_row(key):
    return {"key": key, "miss": True, "value": None}


def cp17(output):
    data = _as_output(output)
    rows = _rows(data.get("reads"))
    facts = []
    seen_miss = set()
    for row in rows:
        if isinstance(row, str):
            facts.append(_miss_row(row))
            seen_miss.add(row)
            continue
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        miss = row.get("miss")
        if miss is None:
            miss = value is None
        miss = bool(miss)
        facts.append({"key": row.get("key"), "miss": miss, "value": None if miss else value})
        if miss:
            seen_miss.add(row.get("key"))
    extra = data.get("miss")
    if isinstance(extra, str):
        extra = [extra]
    if isinstance(extra, list):
        for item in extra:
            key = item if isinstance(item, str) else item.get("key") if isinstance(item, dict) else None
            if key is None or key in seen_miss:
                continue
            facts.append(_miss_row(key))
            seen_miss.add(key)
    return facts


def cp18(output):
    rows = []
    data = _as_output(output)
    if isinstance(data.get("reads"), list):
        rows = data["reads"]
    else:
        for value in data.values():
            if isinstance(value, dict) and any(key in value for key in ("state", "price", "ticket", "refund")):
                rows.append(value)
    return [
        {"ticket": row.get("ticket"), "state": row.get("state"), "price": row.get("price"), "refund": row.get("refund", 0)}
        for row in rows if isinstance(row, dict)
    ]


FACTS = {
    "CP-09": cp09, "CP-10": cp10, "CP-11": cp11, "CP-12": cp12,
    "CP-13": cp13, "CP-14": cp14, "CP-15": cp15, "CP-16": cp16,
    "CP-17": cp17, "CP-18": cp18,
}
