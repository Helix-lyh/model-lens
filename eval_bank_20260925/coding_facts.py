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


def _snapshot_sort_key(value):
    text = str(value)
    if text.isdigit():
        return 0, int(text)
    return 1, text


def _cp09_snapshots(value):
    if isinstance(value, dict):
        pairs = list(value.items())
    elif isinstance(value, list):
        pairs = []
        for index, body in enumerate(value):
            if isinstance(body, dict):
                pairs.append((body.get("id", body.get("snapshot", index)), body))
    else:
        pairs = []
    rows = []
    for ident, body in pairs:
        if not isinstance(body, dict) or ("quota" not in body and "orders" not in body):
            continue
        rows.append({"id": str(ident), "quota": body.get("quota"), "orders": _orders(body.get("orders"))})
    rows.sort(key=lambda row: _snapshot_sort_key(row["id"]))
    return rows


def cp09(output):
    data = _as_output(output)
    return {"quota": data.get("quota"), "orders": _orders(data.get("orders")), "snapshots": _cp09_snapshots(data.get("snapshots"))}


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
        elif isinstance(read, dict):
            maps.append(dict(read))
    return maps


def cp11(output):
    return {"reads": _config_maps(output)}


def _edge_snapshot(value):
    rows = value.get("edges") if isinstance(value, dict) and "edges" in value else value
    if not isinstance(rows, list):
        return None
    found = []
    for row in rows:
        if isinstance(row, dict):
            found.append((row.get("tenant"), row.get("from"), row.get("to")))
        elif isinstance(row, (list, tuple)) and len(row) >= 3 and not isinstance(row[0], (list, dict)):
            found.append((row[0], row[1], row[2]))
        else:
            return None
    return sorted(found)


def _relation_snapshots(value):
    if isinstance(value, dict):
        return [_edge_snapshot(value[key]) for key in sorted(value, key=_snapshot_sort_key)]
    if not isinstance(value, list):
        return []
    flat = value and all(isinstance(item, dict) and "edges" not in item and ("from" in item or "to" in item) for item in value)
    if flat:
        return [_edge_snapshot(value)]
    return [_edge_snapshot(item) for item in value]


def cp12(output):
    data = _as_output(output)
    roots = [row.get("root") for row in _rows(data.get("lookups")) if isinstance(row, dict)]
    edges = []
    for row in _rows(data.get("edges")):
        if isinstance(row, dict):
            edges.append((row.get("tenant"), row.get("from"), row.get("to")))
    return {"roots": roots, "edges": edges, "snapshots": _relation_snapshots(data.get("snapshots"))}


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


def _sum_qty(batches, field):
    total = 0
    saw = False
    for batch in batches:
        if not isinstance(batch, dict) or isinstance(batch.get(field), bool) or not isinstance(batch.get(field), (int, float)):
            return None
        saw = True
        total += batch[field]
    return total if saw else None


def cp14(output):
    data = _as_output(output)
    reads = []
    for row in _rows(data.get("reads")):
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("batches"), list) and row["batches"]:
            free = _sum_qty(row["batches"], "free")
            locked = _sum_qty(row["batches"], "locked")
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
    seen = set()
    raw = data.get("reads")
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                rows.append({"key": key, **value})
            elif value is None:
                rows.append({"key": key, "value": None, "miss": True})
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        miss = row.get("miss")
        if miss is None:
            miss = value is None
        miss = bool(miss)
        if miss and value is not None:
            facts.append({"key": row.get("key"), "miss": True, "value": value})
        elif miss:
            facts.append(_miss_row(row.get("key")))
        else:
            facts.append({"key": row.get("key"), "miss": False, "value": value})
        if row.get("key") is not None:
            seen.add(row.get("key"))
    miss = data.get("miss")
    if isinstance(miss, dict):
        for event_id, key in miss.items():
            if not isinstance(key, str) or key in seen:
                continue
            leaked = None
            if isinstance(raw, dict):
                for slot in (event_id, key):
                    if slot in raw and not isinstance(raw[slot], dict) and raw[slot] is not None:
                        leaked = raw[slot]
                        break
            facts.append({"key": key, "miss": True, "value": leaked} if leaked is not None else _miss_row(key))
            seen.add(key)
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
    found = [
        {"ticket": row.get("ticket"), "state": row.get("state"), "price": row.get("price"), "refund": row.get("refund", 0)}
        for row in rows if isinstance(row, dict)
    ]
    def _num(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return (1, str(value))
        return (0, value)

    return sorted(found, key=lambda row: (str(row["ticket"]), str(row["state"]), _num(row["price"]), _num(row["refund"])))


FACTS = {
    "CP-09": cp09, "CP-10": cp10, "CP-11": cp11, "CP-12": cp12,
    "CP-13": cp13, "CP-14": cp14, "CP-15": cp15, "CP-16": cp16,
    "CP-17": cp17, "CP-18": cp18,
}
