"""Small, independent CP evaluators used to construct expected results.

These functions do not import challenge_refs. They deliberately use different
representations: committed order history, a separate lease table, role closure,
transitive matrices, signed ledger postings, and replayed aggregation history.
Hand-computed boundary examples in tests validate both implementations.
"""

from copy import deepcopy


def orders(data):
    initial = data.get("initial", {})
    states, lines, seen, snapshots, trace = {}, {}, set(), {}, []

    def inventory():
        return {
            sku: initial.get(sku, 0) - sum(
                row.get(sku, 0) for order, row in lines.items()
                if states[order] != "CANCELED"
            )
            for sku in set(initial) | {sku for row in lines.values() for sku in row}
        }

    for event in data.get("events", []):
        eid, op = event["id"], event["op"]
        oid = event.get("order")
        if eid in seen:
            trace.append("DUP")
            continue
        seen.add(eid)
        status = "INVALID"
        if op == "SNAPSHOT":
            snapshots[eid] = (deepcopy(initial), deepcopy(states), deepcopy(lines)); trace.append("SNAP"); continue
        if op == "RESTORE":
            snap = snapshots.get(event.get("snapshot"))
            if snap is not None:
                initial, states, lines = deepcopy(snap[0]), deepcopy(snap[1]), deepcopy(snap[2]); trace.append("RESTORE")
            else:
                trace.append("INVALID")
            continue
        if op == "RETURN":
            pairs = event.get("lines") or []
            current = lines.get(oid, {})
            valid = states.get(oid) == "SHIPPED" and bool(pairs) and all(type(n) is int and n > 0 for _, n in pairs)
            requested = {}
            for key, n in pairs:
                if type(n) is int:
                    requested[key] = requested.get(key, 0) + n
            if states.get(oid) != "SHIPPED":
                trace.append("INVALID")
            elif not valid or any(current.get(sku, 0) < requested.get(sku, 0) for sku in requested):
                trace.append("REJECT")
            else:
                for sku, n in requested.items():
                    current[sku] -= n
                    if current[sku] == 0:
                        del current[sku]
                trace.append("OK")
            continue
        if op == "RESERVE" and oid not in states:
            requested = {
                sku: sum(n for key, n in event.get("lines", []) if key == sku)
                for sku, _ in event.get("lines", [])
            }
            stock = inventory()
            valid = all(type(n) is int and n > 0 for _, n in event.get("lines", []))
            if valid and all(stock.get(sku, 0) >= n for sku, n in requested.items()):
                states[oid], lines[oid], status = "RESERVED", requested, "OK"
            else:
                status = "REJECT"
        elif oid in states:
            transitions = {
                ("RESERVED", "PAY"): "PAID", ("PAID", "SHIP"): "SHIPPED",
                ("RESERVED", "CANCEL"): "CANCELED", ("PAID", "CANCEL"): "CANCELED",
            }
            if (states[oid], op) in transitions:
                states[oid], status = transitions[states[oid], op], "OK"
        trace.append(status)
    stock = inventory()
    return {
        "trace": trace,
        "inventory": [[sku, stock[sku]] for sku in sorted(stock) if stock[sku]],
        "orders": [[oid, states[oid], [] if states[oid] == "CANCELED" else
                    [[sku, n] for sku, n in sorted(lines[oid].items())]]
                   for oid in sorted(states)],
    }


def queue(data):
    definitions = {job["id"]: job for job in data.get("tasks", [])}
    state = {jid: "PENDING" for jid in definitions}
    attempts = dict.fromkeys(definitions, 0)
    leases, trace = {}, []
    for event in data.get("events", []):
        now, op = event["now"], event["op"]
        for jid in list(leases):
            if leases[jid][2] <= now:
                del leases[jid]
                state[jid] = "DEAD" if attempts[jid] == definitions[jid]["max_attempts"] else "PENDING"
        result = "INVALID"
        if op == "POLL":
            available = sorted(
                (jid for jid, status in state.items()
                 if status == "PENDING" and definitions[jid].get("ready", 0) <= now
                 and all(state.get(dep) == "DONE" for dep in definitions[jid].get("depends") or [])),
                key=lambda jid: (-definitions[jid].get("priority", 0),
                                 definitions[jid].get("ready", 0), jid),
            )
            result = None
            if available and event["worker"] not in [value[0] for value in leases.values()]:
                jid = available[0]
                attempts[jid] += 1
                result = f"{jid}:{attempts[jid]}"
                leases[jid] = (event["worker"], result, now + data.get("lease", 5))
                state[jid] = "RUNNING"
        elif op in ("ACK", "FAIL"):
            jid = event["task"]
            lease = leases.get(jid)
            result = "STALE"
            if lease and lease[:2] == (event["worker"], event["token"]):
                del leases[jid]
                if op == "ACK":
                    state[jid], result = "DONE", "OK"
                elif attempts[jid] == definitions[jid]["max_attempts"]:
                    state[jid], result = "DEAD", "DEAD"
                else:
                    state[jid], result = "PENDING", "RETRY"
        elif op == "CANCEL" and state.get(event["task"]) in ("PENDING", "RUNNING"):
            jid = event["task"]
            state[jid], result = "CANCELED", "OK"
            leases.pop(jid, None)
        elif op == "TICK":
            result = "OK"
        trace.append(result)
    return {"trace": trace, "tasks": [[jid, state[jid], attempts[jid]] for jid in sorted(state)]}


def permissions(data):
    parents = data.get("roles", {})
    names = set(parents) | {p for ps in parents.values() for p in ps}
    names |= {r for rs in data.get("users", {}).values() for r in rs}
    closure = {r: {r, *parents.get(r, [])} for r in names}
    for _ in names:
        closure = {r: set().union(*(closure[p] for p in ancestors))
                   for r, ancestors in closure.items()}
    active, result = {}, []
    for event in data.get("events", []):
        if event[0] == "ADD":
            active[event[1]] = event[2]
        elif event[0] == "REMOVE":
            active.pop(event[1], None)
        elif event[0] == "SETROLE":
            parents[event[1]] = list(event[2])
            names.update([event[1], *event[2]])
            closure = {r: {r, *parents.get(r, [])} for r in names}
            for _ in names:
                for role in list(closure):
                    closure[role] |= set().union(*(closure.get(p, {p}) for p in parents.get(role, [])))
        else:
            _, user, action, resource, timestamp = event
            roles = set().union(*(closure[r] for r in data.get("users", {}).get(user, [])))
            effects = []
            for rule in active.values():
                pattern = rule["resource"]
                if rule["role"] not in roles or rule["action"] not in ("*", action):
                    continue
                if "start" in rule and timestamp < rule["start"]:
                    continue
                if "end" in rule and timestamp >= rule["end"]:
                    continue
                if pattern == "*":
                    matched = True
                elif pattern.endswith("*"):
                    prefix = pattern[:-1]
                    rest = resource[len(prefix):] if resource.startswith(prefix) else ""
                    matched = bool(rest) and ":" not in rest
                else:
                    matched = pattern == resource
                if not matched:
                    continue
                effects.append(rule["effect"])
            result.append("ALLOW" if "allow" in effects and "deny" not in effects else "DENY")
    return result


def releases(data):
    env = data.get("environment", "prod")
    changes = {c["id"]: c for c in data.get("changes", [])
               if c["id"] not in data.get("rollback", []) and c.get("env", env) in (env, "*")}
    ids = sorted(changes)
    n = len(ids)
    before = [[False] * n for _ in ids]
    for i, first in enumerate(ids):
        for j, second in enumerate(ids):
            change = changes[second]
            before[i][j] = first in change.get("after", []) or changes[first]["service"] in data.get("dependencies", {}).get(change["service"], [])
    for k in range(n):
        for i in range(n):
            for j in range(n):
                before[i][j] |= before[i][k] and before[k][j]
    if any(before[i][i] for i in range(n)):
        return {"status": "CYCLE", "order": [], "config": [], "conflicts": []}
    remaining, order = set(range(n)), []
    while remaining:
        layer = sorted(i for i in remaining if not any(before[j][i] for j in remaining))
        order.extend(ids[i] for i in layer)
        remaining.difference_update(layer)
    writes = []
    for cid in ids:
        change = changes[cid]
        write = {key: ("delete", None) for key in change.get("delete", [])}
        write.update({key: ("set", value) for key, value in change.get("set", {}).items()})
        writes.append(write)
    def concrete(change):
        return change.get("env", env) != "*"

    specific = {(changes[cid]["service"], key) for cid in changes if concrete(changes[cid]) for key in writes[ids.index(cid)]}
    conflicts = []
    for i in range(n):
        for j in range(i + 1, n):
            left, right = changes[ids[i]], changes[ids[j]]
            if left["service"] != right["service"] or concrete(left) != concrete(right) or before[i][j] or before[j][i]:
                continue
            shared = [key for key in writes[i].keys() & writes[j].keys()
                      if concrete(left) or (left["service"], key) not in specific]
            if any(writes[i][key] != writes[j][key] for key in shared):
                conflicts.append([ids[i], ids[j]])
    if conflicts:
        return {"status": "CONFLICT", "order": order, "config": [], "conflicts": conflicts}
    config = deepcopy(data.get("base", {}))
    for service, patch in data.get("overlays", {}).get(env, {}).items():
        config.setdefault(service, {}).update(patch)
    for cid in order:
        change = changes[cid]
        target = config.setdefault(change["service"], {})
        starred = not concrete(change)
        for key in change.get("delete", []):
            if starred and (change["service"], key) in specific: continue
            target.pop(key, None)
        for key, value in change.get("set", {}).items():
            if starred and (change["service"], key) in specific: continue
            target[key] = value
    return {"status": "OK", "order": order,
            "config": [[service, [[key, value] for key, value in sorted(config[service].items())]] for service in sorted(config)],
            "conflicts": []}


def settlement(data):
    treasury = data.get("treasury", "_fees")
    opening = {**data.get("accounts", {})}
    opening.setdefault(treasury, 0)
    transactions, postings, batches, operations, trace = {}, [], set(), set(), []

    def balances(extra=()):
        return {account: opening[account] + sum(n for key, n in [*postings, *extra] if key == account)
                for account in opening}

    for event in data.get("events", []):
        op, key = event[:2]
        used = batches if op == "BATCH" else operations
        if key in used:
            trace.append("DUP")
            continue
        used.add(key)
        if op == "BATCH":
            rows, delta = event[2], []
            valid = len({row[0] for row in rows}) == len(rows)
            for txid, source, dest, amount, fee in rows:
                reusable = txid in transactions and transactions[txid][1] == "REVERSED"
                valid &= (txid not in transactions or reusable) and source in opening and dest in opening and source != dest and amount > 0 and fee >= 0
                delta.extend([(source, -amount - fee), (dest, amount), (treasury, fee)])
            if not valid or min(balances(delta).values(), default=0) < 0:
                trace.append("REJECT")
                continue
            postings.extend(delta)
            for row in rows:
                transactions[row[0]] = (row, "SETTLED")
        else:
            txid = event[2]
            if txid not in transactions or transactions[txid][1] != "SETTLED":
                trace.append("INVALID")
                continue
            row = transactions[txid][0]
            _, source, dest, amount, fee = row
            delta = [(source, amount + fee), (dest, -amount), (treasury, -fee)]
            if min(balances(delta).values(), default=0) < 0:
                trace.append("INVALID")
                continue
            postings.extend(delta)
            transactions[txid] = (row, "REVERSED")
        trace.append("OK")
    final = balances()
    return {"trace": trace, "balances": [[key, final[key]] for key in sorted(final) if final[key]],
            "transactions": [[key, transactions[key][1]] for key in sorted(transactions)]}


def aggregation(data):
    width, output = data["window"], []
    events = data.get("events", [])
    for end, event in enumerate(events):
        if event[0] not in ("QUERY", "SNAPSHOT"):
            continue
        ingested, retracted, operations, sealed = {}, set(), set(), set()
        for prior in events[:end]:
            if prior[0] == "INGEST":
                if prior[1] not in ingested:
                    start = prior[3] // width * width
                    ingested[prior[1]] = (prior[2], prior[3], prior[4], (prior[2], start) not in sealed)
            elif prior[0] == "SEAL" and prior[1] not in operations:
                operations.add(prior[1])
                sealed.add((prior[2], prior[3] // width * width))
            elif prior[0] == "RETRACT" and prior[1] not in operations:
                operations.add(prior[1])
                if prior[2] in ingested:
                    retracted.add(prior[2])
            elif prior[0] == "AMEND" and prior[1] not in operations:
                operations.add(prior[1])
                row = ingested.get(prior[2])
                if row and row[3] and prior[2] not in retracted:
                    who, ts, _, _active = row
                    old, new = ts // width * width, prior[3] // width * width
                    if (who, old) not in sealed and (who, new) not in sealed:
                        ingested[prior[2]] = (who, prior[3], prior[4], True)
        active = {eid: row for eid, row in ingested.items() if row[3] and eid not in retracted}
        keys = {(entity, timestamp // width * width) for entity, timestamp, _, _flag in active.values()}
        if event[0] == "QUERY":
            keys = {(event[1], event[2] // width * width)}
        results = []
        for entity, start in sorted(keys):
            ids = sorted(eid for eid, (who, ts, _, _flag) in active.items()
                         if who == entity and start <= ts < start + width)
            results.append({"entity": entity, "start": start, "count": len(ids),
                            "sum": sum(active[eid][2] for eid in ids), "ids": ids})
        output.append(results[0] if event[0] == "QUERY" else results)
    return output


def scheduling(data):
    """Time-event simulation with state reconstructed from the schedule."""
    jobs = {j["id"]: j for j in data.get("jobs", [])}
    canceled, started, schedule = set(), set(), []
    budgets = {key: int(value) for key, value in data.get("budgets", {}).items()}
    blackouts = [(int(a), int(b)) for a, b in data.get("blackouts", []) if int(a) < int(b)]
    def blocked(start, end): return any(start < b and a < end for a, b in blackouts)
    moments = {0, *(j.get("release", 0) for j in jobs.values()), *(b for _, b in blackouts),
               *(c["time"] for c in data.get("cancel", []))}
    while moments:
        time = min(moments)
        moments.remove(time)
        done = {row[0] for row in schedule if row[2] <= time}
        running = [row for row in schedule if row[2] > time]
        canceled.update(c["id"] for c in data.get("cancel", [])
                        if c["time"] == time and c["id"] in jobs and c["id"] not in started)
        candidates = sorted(
            (j for jid, j in jobs.items()
             if jid not in started | canceled and j.get("release", 0) <= time and set(j.get("deps", [])) <= done),
            key=lambda j: (-j.get("priority", 0), j.get("deadline", 10**9), j["id"]),
        )
        for job in candidates:
            free = sorted(set(range(data.get("workers", 1))) - {row[3] for row in running})
            if not free:
                break
            if any(sum(resource in jobs[row[0]].get("needs", []) for row in running) >= data.get("resources", {}).get(resource, 0)
                   for resource in job.get("needs", [])):
                continue
            finish = time + job["duration"]
            pool = job.get("pool")
            if blocked(time, finish):
                continue
            if pool is not None and budgets.get(pool, 0) < job["duration"]:
                continue
            if pool is not None:
                budgets[pool] -= job["duration"]
            row = [job["id"], time, finish, free[0], finish > job.get("deadline", 10**9)]
            schedule.append(row)
            running.append(row)
            started.add(job["id"])
            moments.add(finish)
    return {"schedule": schedule,
            "states": [[jid, "DONE" if jid in started else "CANCELED" if jid in canceled else "PENDING"] for jid in sorted(jobs)]}


def rules(data):
    values = deepcopy(data.get("facts", {}))
    fired, conflicts, claims = [], [], {}
    stopped = False
    base = deepcopy(values)

    def differs(field):
        if (field in base) != (field in values):
            return True
        return field in base and base[field] != values[field]

    def matches(condition):
        if "not" in condition:
            return not matches(condition["not"])
        if "all" in condition:
            return all(map(matches, condition["all"]))
        if "any" in condition:
            return any(map(matches, condition["any"]))
        field, op = condition.get("field"), condition.get("op")
        value, target = values.get(field), condition.get("value")
        if op == "changed": return differs(field)
        if op == "exists": return field in values
        if op == "eq": return value == target
        if op == "neq": return value != target
        if op == "in": return value in target
        if op == "contains": return isinstance(value, list) and target in value
        if op == "gte": return type(value) in (int, float) and value >= target
        if op == "lte": return type(value) in (int, float) and value <= target
        return False

    for phase in ("pre", "main", "post"):
        base = deepcopy(values)
        selected = sorted((r for r in data.get("rules", []) if r.get("phase", "main") == phase),
                          key=lambda r: (-r.get("priority", 0), r["id"]))
        for rule in selected:
            if stopped or "when" not in rule or not matches(rule["when"]):
                continue
            fired.append(rule["id"])
            for key in sorted(rule.get("set", {})):
                value = rule["set"][key]
                if (phase, key) in claims and claims[phase, key][1] != value:
                    conflicts.append([claims[phase, key][0], rule["id"], key])
                else:
                    values[key] = deepcopy(value)
                    claims.setdefault((phase, key), (rule["id"], deepcopy(value)))
            for key, value in rule.get("add", {}).items():
                if key not in values:
                    values[key] = []
                if value not in values[key]:
                    values[key].append(deepcopy(value))
            for key in rule.get("remove", []):
                if key in values:
                    values.pop(key)
            stopped = bool(rule.get("stop", False))
    return {"facts": [[key, value] for key, value in sorted(values.items())],
            "fired": fired, "conflicts": conflicts, "stopped": stopped}


ORACLES = {
    "CP-01": orders, "CP-02": queue, "CP-03": permissions, "CP-04": releases,
    "CP-05": settlement, "CP-06": aggregation, "CP-07": scheduling, "CP-08": rules,
}
