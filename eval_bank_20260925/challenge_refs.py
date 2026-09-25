"""CP-01..CP-08 的可审计参考实现。

这些题刻意使用小输入；难点来自跨事件状态、原子提交、冲突优先级和历史引用，
而不是靠把图或数组放大到超时。
"""


def order_processor(data):
    stock = {k: int(v) for k, v in data.get("initial", {}).items()}
    orders = {}; used = set(); snapshots = {}; trace = []
    for ev in data.get("events", []):
        op, eid = ev["op"], ev["id"]
        order = ev.get("order")
        if eid in used: trace.append("DUP"); continue
        used.add(eid)
        if op == "SNAPSHOT":
            snapshots[eid] = (dict(stock), {k: {"state": v["state"], "lines": dict(v["lines"])} for k, v in orders.items()})
            trace.append("SNAP"); continue
        if op == "RESTORE":
            snap = snapshots.get(ev.get("snapshot"))
            if snap is None:
                trace.append("INVALID"); continue
            stock = dict(snap[0]); orders = {k: {"state": v["state"], "lines": dict(v["lines"])} for k, v in snap[1].items()}
            trace.append("RESTORE"); continue
        if op == "RESERVE":
            order = ev["order"]
            if order in orders: trace.append("INVALID"); continue
            merged = {}; valid = True
            for sku, qty in ev.get("lines", []):
                if not isinstance(qty, int) or qty <= 0: valid = False
                merged[sku] = merged.get(sku, 0) + qty
            if not valid or any(stock.get(sku, 0) < qty for sku, qty in merged.items()): trace.append("REJECT"); continue
            for sku, qty in merged.items(): stock[sku] = stock.get(sku, 0) - qty
            orders[order] = {"state": "RESERVED", "lines": merged}; trace.append("OK")
        elif op in ("PAY", "SHIP", "CANCEL"):
            order = orders.get(ev["order"])
            if order is None: trace.append("INVALID"); continue
            state = order["state"]
            if op == "PAY" and state == "RESERVED": order["state"] = "PAID"; trace.append("OK")
            elif op == "SHIP" and state == "PAID": order["state"] = "SHIPPED"; trace.append("OK")
            elif op == "CANCEL" and state in ("RESERVED", "PAID"):
                for sku, qty in order["lines"].items(): stock[sku] = stock.get(sku, 0) + qty
                order["state"] = "CANCELED"; order["lines"] = {}; trace.append("OK")
            else: trace.append("INVALID")
        elif op == "RETURN":
            order = orders.get(ev.get("order"))
            if order is None or order["state"] != "SHIPPED": trace.append("INVALID"); continue
            merged = {}; valid = True
            for sku, qty in ev.get("lines", []):
                if not isinstance(qty, int) or qty <= 0: valid = False
                merged[sku] = merged.get(sku, 0) + qty
            if not merged or not valid or any(order["lines"].get(sku, 0) < qty for sku, qty in merged.items()):
                trace.append("REJECT"); continue
            for sku, qty in merged.items():
                order["lines"][sku] -= qty
                if order["lines"][sku] == 0: del order["lines"][sku]
                stock[sku] = stock.get(sku, 0) + qty
            trace.append("OK")
        else: trace.append("INVALID")
    return {"trace": trace, "inventory": [[k, stock[k]] for k in sorted(stock) if stock[k] != 0], "orders": [[k, orders[k]["state"], [[s, q] for s, q in sorted(orders[k]["lines"].items())]] for k in sorted(orders)]}


def task_queue(data):
    jobs = {t["id"]: {**t, "state": "PENDING", "attempts": 0, "worker": None, "token": None, "until": None} for t in data.get("tasks", [])}
    lease = data.get("lease", 5); workers = {}; trace = []

    def expire(now):
        for t in jobs.values():
            if t["state"] == "RUNNING" and t["until"] <= now:
                workers.pop(t["worker"], None); t["worker"] = t["token"] = t["until"] = None
                t["state"] = "DEAD" if t["attempts"] >= t["max_attempts"] else "PENDING"

    for ev in data.get("events", []):
        now = ev.get("now", 0); expire(now); op = ev["op"]
        if op == "POLL":
            worker = ev["worker"]
            if worker in workers: trace.append(None); continue
            candidates = [t for t in jobs.values() if t["state"] == "PENDING" and t.get("ready", 0) <= now and all(jobs.get(dep, {}).get("state") == "DONE" for dep in t.get("depends") or [])]
            candidates.sort(key=lambda t: (-t.get("priority", 0), t.get("ready", 0), t["id"]))
            if not candidates: trace.append(None); continue
            t = candidates[0]; t["state"] = "RUNNING"; t["worker"] = worker; t["attempts"] += 1; t["token"] = f"{t['id']}:{t['attempts']}"; t["until"] = now + lease; workers[worker] = t["id"]; trace.append(t["token"])
        elif op in ("ACK", "FAIL"):
            t = jobs.get(ev.get("task")); ok = bool(t and t["state"] == "RUNNING" and t["worker"] == ev.get("worker") and t["token"] == ev.get("token"))
            if not ok: trace.append("STALE"); continue
            workers.pop(t["worker"], None); t["worker"] = t["token"] = t["until"] = None
            if op == "ACK": t["state"] = "DONE"; trace.append("OK")
            elif t["attempts"] >= t["max_attempts"]: t["state"] = "DEAD"; trace.append("DEAD")
            else: t["state"] = "PENDING"; trace.append("RETRY")
        elif op == "CANCEL":
            t = jobs.get(ev.get("task"))
            if t and t["state"] in ("PENDING", "RUNNING"):
                if t["worker"] is not None: workers.pop(t["worker"], None)
                t["state"] = "CANCELED"; t["worker"] = t["token"] = t["until"] = None; trace.append("OK")
            else: trace.append("INVALID")
        elif op == "TICK": trace.append("OK")
        else: trace.append("INVALID")
    return {"trace": trace, "tasks": [[k, jobs[k]["state"], jobs[k]["attempts"]] for k in sorted(jobs)]}


def permission_engine(data):
    parents = data.get("roles", {}); users = data.get("users", {}); rules = {}; results = []

    def inherited(role):
        seen = set(); stack = [role]
        while stack:
            cur = stack.pop()
            if cur in seen: continue
            seen.add(cur); stack.extend(parents.get(cur, []))
        return seen

    def check(user, action, resource, when):
        roles = set()
        for role in users.get(user, []): roles |= inherited(role)
        applicable = []
        for seq, rule in rules.values():
            if rule["role"] not in roles or not (rule.get("start", -10**18) <= when < rule.get("end", 10**18)): continue
            if rule.get("action", "*") not in ("*", action): continue
            pattern = rule.get("resource", "*")
            if pattern == "*":
                matched = True
            elif pattern.endswith("*"):
                prefix = pattern[:-1]
                rest = resource[len(prefix):] if resource.startswith(prefix) else None
                matched = rest is not None and rest != "" and ":" not in rest
            else:
                matched = pattern == resource
            if not matched: continue
            applicable.append(((int(pattern == resource), int(rule.get("action", "*") == action)), rule["effect"], seq))
        if any(effect == "deny" for _, effect, _ in applicable): return "DENY"
        if not applicable: return "DENY"
        best = max(s for s, _, _ in applicable)
        return "ALLOW" if any(effect == "allow" and s == best for s, effect, _ in applicable) else "DENY"

    for seq, ev in enumerate(data.get("events", [])):
        if ev[0] == "ADD": rules[ev[1]] = (seq, ev[2])
        elif ev[0] == "REMOVE": rules.pop(ev[1], None)
        elif ev[0] == "SETROLE": parents[ev[1]] = list(ev[2])
        elif ev[0] == "CHECK": results.append(check(ev[1], ev[2], ev[3], ev[4]))
    return results


def release_plan(data):
    env = data.get("environment", "prod"); config = {s: dict(v) for s, v in data.get("base", {}).items()}
    for s, patch in data.get("overlays", {}).get(env, {}).items(): config.setdefault(s, {}).update(patch)
    rolled = set(data.get("rollback", [])); changes = [c for c in data.get("changes", []) if c["id"] not in rolled and c.get("env", env) in (env, "*")]; by_id = {c["id"]: c for c in changes}
    graph = {c["id"]: set() for c in changes}
    for c in changes:
        for dep in c.get("after", []):
            if dep in graph: graph[c["id"]].add(dep)
        for dep_service in data.get("dependencies", {}).get(c["service"], []):
            for other in changes:
                if other["service"] == dep_service: graph[c["id"]].add(other["id"])
    work = {k: set(v) for k, v in graph.items()}; order = []
    while True:
        ready = sorted(k for k, deps in work.items() if not deps and k not in order)
        if not ready: break
        order.extend(ready)
        for node in work: work[node] -= set(ready)
    if len(order) != len(changes): return {"status": "CYCLE", "order": [], "config": [], "conflicts": []}
    def reaches(start, target):
        seen = set(); stack = list(graph.get(start, ()))
        while stack:
            node = stack.pop()
            if node == target: return True
            if node not in seen:
                seen.add(node); stack.extend(graph.get(node, ()))
        return False
    def written_keys(change):
        return set(change.get("set", {})) | set(change.get("delete", []))

    def concrete(change):
        return change.get("env", env) != "*"

    specific = {(c["service"], key) for c in changes if concrete(c) for key in written_keys(c)}
    conflicts = []
    for i, c in enumerate(changes):
        for p in changes[i + 1:]:
            if p["service"] != c["service"] or concrete(c) != concrete(p): continue
            for key in written_keys(c) & written_keys(p):
                if not concrete(c) and (c["service"], key) in specific: continue
                a, b = c["id"], p["id"]
                if reaches(a, b) or reaches(b, a): continue
                va = c.get("set", {}).get(key, "__DELETE__"); vb = p.get("set", {}).get(key, "__DELETE__")
                if va != vb: conflicts.append(sorted([a, b]))
    if conflicts: return {"status": "CONFLICT", "order": order, "config": [], "conflicts": [list(x) for x in sorted(set(tuple(x) for x in conflicts))]}
    for cid in order:
        c = by_id[cid]; target = config.setdefault(c["service"], {})
        for key in c.get("delete", []):
            if not concrete(c) and (c["service"], key) in specific: continue
            target.pop(key, None)
        for key, value in c.get("set", {}).items():
            if not concrete(c) and (c["service"], key) in specific: continue
            target[key] = value
    return {"status": "OK", "order": order, "config": [[s, [[k, config[s][k]] for k in sorted(config[s])]] for s in sorted(config)], "conflicts": []}


def ledger(data):
    balances = {k: int(v) for k, v in data.get("accounts", {}).items()}; treasury = data.get("treasury", "_fees"); balances.setdefault(treasury, 0)
    batches = set(); operations = set(); txs = {}; trace = []
    for ev in data.get("events", []):
        op = ev[0]
        if op == "BATCH":
            bid, rows = ev[1], ev[2]
            if bid in batches: trace.append("DUP"); continue
            batches.add(bid); seen = set(); delta = {k: 0 for k in balances}; valid = True
            for txid, src, dst, amount, fee in rows:
                if txid in seen or (txid in txs and txs[txid]["state"] != "REVERSED") or src == dst or src not in balances or dst not in balances or amount <= 0 or fee < 0: valid = False; continue
                seen.add(txid); delta[src] -= amount + fee; delta[dst] += amount; delta[treasury] += fee
            if not valid or any(balances[k] + delta[k] < 0 for k in balances): trace.append("REJECT"); continue
            for k, v in delta.items(): balances[k] += v
            for txid, src, dst, amount, fee in rows: txs[txid] = {"src": src, "dst": dst, "amount": amount, "fee": fee, "state": "SETTLED"}
            trace.append("OK")
        elif op == "REVERSE":
            oid, txid = ev[1], ev[2]
            if oid in operations: trace.append("DUP"); continue
            operations.add(oid); tx = txs.get(txid)
            if tx is None or tx["state"] != "SETTLED": trace.append("INVALID"); continue
            delta = {k: 0 for k in balances}; delta[tx["src"]] += tx["amount"] + tx["fee"]; delta[tx["dst"]] -= tx["amount"]; delta[treasury] -= tx["fee"]
            if any(balances[k] + delta[k] < 0 for k in balances): trace.append("INVALID"); continue
            for k, v in delta.items(): balances[k] += v
            tx["state"] = "REVERSED"; trace.append("OK")
        else: trace.append("INVALID")
    return {"trace": trace, "balances": [[k, balances[k]] for k in sorted(balances) if balances[k] != 0], "transactions": [[k, txs[k]["state"]] for k in sorted(txs)]}


def event_aggregate(data):
    width = data["window"]; records = {}; used_ops = set(); sealed = set(); results = []

    def window_start(timestamp):
        return (timestamp // width) * width

    for ev in data.get("events", []):
        op = ev[0]
        if op == "INGEST":
            _, eid, entity, timestamp, value = ev
            if eid not in records:
                start = window_start(timestamp)
                records[eid] = {"entity": entity, "time": timestamp, "value": value, "active": (entity, start) not in sealed}
        elif op == "SEAL":
            _, oid, entity, timestamp = ev
            if oid in used_ops: continue
            used_ops.add(oid)
            sealed.add((entity, window_start(timestamp)))
        elif op == "RETRACT":
            _, oid, eid = ev
            if oid in used_ops: continue
            used_ops.add(oid)
            if eid in records: records[eid]["active"] = False
        elif op == "AMEND":
            _, oid, eid, timestamp, value = ev
            if oid in used_ops: continue
            used_ops.add(oid)
            row = records.get(eid)
            if row and row["active"]:
                old, new = window_start(row["time"]), window_start(timestamp)
                if (row["entity"], old) not in sealed and (row["entity"], new) not in sealed:
                    row["time"] = timestamp; row["value"] = value
        elif op == "QUERY":
            _, entity, timestamp = ev; start = (timestamp // width) * width; rows = [(eid, r) for eid, r in records.items() if r["active"] and r["entity"] == entity and start <= r["time"] < start + width]
            results.append({"entity": entity, "start": start, "count": len(rows), "sum": sum(r["value"] for _, r in rows), "ids": sorted(eid for eid, _ in rows)})
        elif op == "SNAPSHOT":
            buckets = {}
            for eid, r in records.items():
                if not r["active"]: continue
                key = (r["entity"], window_start(r["time"])); item = buckets.setdefault(key, {"entity": key[0], "start": key[1], "count": 0, "sum": 0, "ids": []}); item["count"] += 1; item["sum"] += r["value"]; item["ids"].append(eid)
            results.append(sorted(({**v, "ids": sorted(v["ids"])} for v in buckets.values()), key=lambda x: (x["entity"], x["start"])))
    return results


def resource_schedule(data):
    jobs = {j["id"]: {**j, "state": "PENDING"} for j in data.get("jobs", [])}; capacities = data.get("resources", {}); workers = [None] * data.get("workers", 1); running = {}; schedule = []; cancel = {}; budgets = {k: int(v) for k, v in data.get("budgets", {}).items()}
    for c in data.get("cancel", []): cancel.setdefault(c["time"], set()).add(c["id"])
    t = 0
    blackouts = [(int(a), int(b)) for a, b in data.get("blackouts", []) if int(a) < int(b)]
    def blocked(start, end): return any(start < b and a < end for a, b in blackouts)
    while any(j["state"] == "PENDING" for j in jobs.values()) or running:
        for jid, run in list(running.items()):
            if run["end"] == t: jobs[jid]["state"] = "DONE"; workers[run["worker"]] = None; del running[jid]
        for jid in cancel.get(t, set()):
            if jobs.get(jid, {}).get("state") == "PENDING": jobs[jid]["state"] = "CANCELED"
        usage = {r: 0 for r in capacities}
        for run in running.values():
            for r in run["needs"]: usage[r] = usage.get(r, 0) + 1
        ready = [j for j in jobs.values() if j["state"] == "PENDING" and j.get("release", 0) <= t and all(jobs.get(d, {}).get("state") == "DONE" for d in j.get("deps", []))]
        ready.sort(key=lambda j: (-j.get("priority", 0), j.get("deadline", 10**9), j["id"]))
        for j in ready:
            slot = next((i for i, x in enumerate(workers) if x is None), None)
            if slot is None or any(usage.get(r, 0) >= capacities.get(r, 0) for r in j.get("needs", [])): continue
            end = t + j["duration"]
            pool = j.get("pool")
            if blocked(t, end): continue
            if pool is not None and budgets.get(pool, 0) < j["duration"]: continue
            if pool is not None: budgets[pool] -= j["duration"]
            workers[slot] = j["id"]; j["state"] = "RUNNING"; running[j["id"]] = {"worker": slot, "end": end, "needs": j.get("needs", [])}; schedule.append([j["id"], t, end, slot, end > j.get("deadline", 10**9)])
            for r in j.get("needs", []): usage[r] = usage.get(r, 0) + 1
        pending = [j for j in jobs.values() if j["state"] == "PENDING"]
        if not pending:
            if running:
                t = min(run["end"] for run in running.values())
            continue
        if running:
            t += 1
            continue
        future = [j.get("release", t) for j in pending if j.get("release", t) > t] + [b for _, b in blackouts if b > t]
        if future:
            t = min(future)
        else:
            # No running task, no future release, and no assignment is possible:
            # unresolved dependencies or permanently unavailable resources terminate
            # the simulation with those jobs still PENDING.
            break
    return {"schedule": schedule, "states": [[k, jobs[k]["state"]] for k in sorted(jobs)]}


def rule_engine(data):
    facts = dict(data.get("facts", {})); fired = []; conflicts = []; written = {}; stopped = False; phases = {"pre": 0, "main": 1, "post": 2}
    rules = sorted(data.get("rules", []), key=lambda r: (phases.get(r.get("phase", "main"), 1), -r.get("priority", 0), r["id"]))

    def clone(value):
        if isinstance(value, dict):
            return {key: clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clone(item) for item in value]
        return value

    phase_base = clone(facts)

    def changed(field):
        if (field in phase_base) != (field in facts): return True
        return field in phase_base and phase_base[field] != facts[field]

    def predicate(p):
        if "all" in p: return all(predicate(x) for x in p["all"])
        if "any" in p: return any(predicate(x) for x in p["any"])
        if "not" in p: return not predicate(p["not"])
        field = p.get("field"); op = p.get("op"); value = facts.get(field)
        if op == "changed": return changed(field)
        if op == "exists": return field in facts
        if op == "eq": return value == p.get("value")
        if op == "neq": return value != p.get("value")
        if op == "in": return value in p.get("value", [])
        if op == "contains": return isinstance(value, list) and p.get("value") in value
        if op == "gte": return isinstance(value, (int, float)) and value >= p.get("value")
        if op == "lte": return isinstance(value, (int, float)) and value <= p.get("value")
        return False

    current = None
    for rule in rules:
        phase = rule.get("phase", "main")
        if phase != current:
            current = phase
            phase_base = clone(facts)
        if stopped or not predicate(rule.get("when", {"op": "exists", "field": "__always__"})): continue
        fired.append(rule["id"])
        for key, value in rule.get("set", {}).items():
            prior = written.get((phase, key))
            if prior is not None and prior[1] != value:
                conflicts.append([prior[0], rule["id"], key]); continue
            facts[key] = value; written[(phase, key)] = (rule["id"], value)
        for key, value in rule.get("add", {}).items():
            if key not in facts: facts[key] = []
            arr = facts[key]
            if value not in arr: arr.append(value)
        for key in rule.get("remove", []):
            if key in facts: facts.pop(key, None)
        if rule.get("stop"): stopped = True
    return {"facts": [[k, facts[k]] for k in sorted(facts)], "fired": fired, "conflicts": conflicts, "stopped": stopped}
