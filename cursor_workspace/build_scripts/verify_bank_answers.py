"""Verify Python bank tests and structure tests against known-good answers."""

from __future__ import annotations

from src.bank import repo_root
from src.grade import run_python_sandbox

ROOT = repo_root()

PY = {
    "bank/tests/b01_shelf.py": """
def apply_ops(ops):
    bins = {"A": 0, "B": 0, "C": 0}
    nxt = {"A": "B", "B": "C", "C": "A"}
    for raw in ops:
        parts = raw.split()
        kind = parts[0]
        if kind == "+":
            bins[parts[1]] += int(parts[2])
        elif kind == "-":
            x, n = parts[1], int(parts[2])
            if bins[x] >= n:
                bins[x] -= n
        elif kind == ">":
            x, y = parts[1], parts[2]
            bins[y] += bins[x]
            bins[x] = 0
        elif kind == "?":
            x = parts[1]
            if bins[x] > 0:
                bins[x] -= 1
                bins[nxt[x]] += 1
    return bins
""",
    "bank/tests/b03_freeze.py": """
class FreezeBag:
    def __init__(self, capacity):
        self.cap = capacity
        self.order = []
        self.vals = {}
        self.frozen = set()

    def _touch(self, key):
        self.order = [k for k in self.order if k != key]
        self.order.append(key)

    def put(self, key, value):
        if key in self.vals:
            self.vals[key] = value
            self._touch(key)
            return
        if len(self.vals) >= self.cap:
            victim = next((k for k in self.order if k not in self.frozen), None)
            if victim is None:
                return
            del self.vals[victim]
            self.order = [k for k in self.order if k != victim]
        self.vals[key] = value
        self._touch(key)

    def get(self, key):
        return self.vals.get(key)

    def freeze(self, key):
        if key in self.vals:
            self.frozen.add(key)
""",
    "bank/tests/b04_pack_runs.py": """
def pack_runs(xs):
    if not xs:
        return []
    out = []
    cur, cnt = xs[0], 1
    for x in xs[1:]:
        if x == cur:
            cnt += 1
        else:
            out.append((cur, cnt))
            cur, cnt = x, 1
    out.append((cur, cnt))
    return out
""",
    "bank/tests/b09_tag_scores.py": """
import re

_SCORE = re.compile(r"^-?\\d+$")


def tag_scores(items):
    out = {}
    for item in items:
        tag, sep, score = item.partition(":")
        if not sep or not tag or not _SCORE.fullmatch(score):
            continue
        out[tag] = out.get(tag, 0) + int(score)
    return out
""",
    "bank/tests/b10_render.py": """
import re

_NAME = re.compile(r"\\{([A-Za-z0-9_]+)\\}")


def render(template, vars):
    out = []
    i = 0
    n = len(template)
    while i < n:
        if template.startswith("{{", i):
            out.append("{")
            i += 2
            continue
        if template.startswith("}}", i):
            out.append("}")
            i += 2
            continue
        if template[i] == "{":
            m = _NAME.match(template, i)
            if m:
                name = m.group(1)
                out.append(vars[name] if name in vars else m.group(0))
                i = m.end()
                continue
        out.append(template[i])
        i += 1
    return "".join(out)
""",
    "bank/tests/b11_limiter.py": """
class SlidingLimiter:
    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self.allowed = []

    def allow(self, ts):
        lo = ts - self.window
        self.allowed = [t for t in self.allowed if t > lo]
        if len(self.allowed) < self.limit:
            self.allowed.append(ts)
            return True
        return False
""",
    "bank/tests/b12_plan_tasks.py": """
import heapq


def plan_tasks(tasks, deps):
    pairs = {(a, b) for a, b in deps}
    indeg = {t: 0 for t in tasks}
    after = {t: [] for t in tasks}
    for a, b in pairs:
        indeg[a] += 1
        after[b].append(a)
    ready = [t for t in tasks if indeg[t] == 0]
    heapq.heapify(ready)
    out = []
    while ready:
        t = heapq.heappop(ready)
        out.append(t)
        for nxt in after[t]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(ready, nxt)
    return out if len(out) == len(tasks) else None
""",
    "bank/tests/b13_replay_counter.py": """
def replay_counter(log):
    balance = 0
    seen = set()
    accepted, rejected = [], []
    debits = []
    for event_id, kind, amount in log:
        if event_id in seen:
            rejected.append(event_id)
            continue
        seen.add(event_id)
        if kind == "credit":
            balance += amount
            accepted.append(event_id)
        elif kind == "debit":
            if amount <= balance:
                balance -= amount
                debits.append([amount, 0])
                accepted.append(event_id)
            else:
                rejected.append(event_id)
        elif kind == "refund":
            for debit in debits:
                if debit[0] - debit[1] >= amount:
                    debit[1] += amount
                    balance += amount
                    accepted.append(event_id)
                    break
            else:
                rejected.append(event_id)
        else:
            rejected.append(event_id)
    return {"balance": balance, "accepted": accepted, "rejected": rejected}
""",
    "bank/tests/b14_merge_budget.py": """
def merge_budget(intervals, budget):
    if type(budget) is not int or budget < 0:
        return {"ok": False, "intervals": [], "reason": "invalid"}
    if any(type(pair) not in (tuple, list) or len(pair) != 2 or type(pair[0]) is not int or type(pair[1]) is not int or pair[0] > pair[1] for pair in intervals):
        return {"ok": False, "intervals": [], "reason": "invalid"}
    merged = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], right)
        else:
            merged.append([left, right])
    if sum(right - left + 1 for left, right in merged) > budget:
        return {"ok": False, "intervals": [], "reason": "budget_exceeded"}
    return {"ok": True, "intervals": [tuple(pair) for pair in merged], "reason": "empty"}
""",
    "bank/tests/b15_knapsack.py": """
def bounded_knapsack(items, capacity):
    if type(capacity) is not int or capacity < 0:
        return {"value": 0, "weight": 0, "indices": []}
    best = (0, 0, [])
    for mask in range(1 << len(items)):
        chosen = [i for i in range(len(items)) if mask & (1 << i)]
        weight = sum(items[i][0] for i in chosen)
        value = sum(items[i][1] for i in chosen)
        if weight > capacity:
            continue
        if value > best[0] or (value == best[0] and chosen < best[2]):
            best = (value, weight, chosen)
    return {"value": best[0], "weight": best[1], "indices": best[2]}
""",
    "bank/tests/b16_mvcc.py": """
def apply_transactions(initial, txns):
    state = dict(initial)
    statuses = {}
    versions = {key: 0 for key in state}
    next_version = 1
    for txn in sorted(txns, key=lambda x: x["commit"]):
        if any(versions.get(key, 0) > txn["begin"] for key in txn["writes"]):
            statuses[txn["id"]] = "ABORT"
            continue
        statuses[txn["id"]] = "COMMIT"
        for key, value in txn["writes"].items():
            state[key] = value
            versions[key] = next_version
        next_version += 1
    return {"state": state, "statuses": statuses}
""",
    "bank/tests/b17_order_events.py": """
def order_events(events):
    state = "CREATED"
    applied, rejected, seen = [], [], set()
    transitions = {
        ("CREATED", "PAY"): "PAID",
        ("PAID", "SHIP"): "SHIPPED",
        ("SHIPPED", "DELIVER"): "DELIVERED",
        ("PAID", "REFUND"): "REFUNDED",
        ("SHIPPED", "REFUND"): "REFUNDED",
        ("CREATED", "CANCEL"): "CANCELLED",
    }
    for event_id, event in events:
        if event_id in seen:
            continue
        seen.add(event_id)
        next_state = transitions.get((state, event))
        if next_state is None:
            rejected.append(event_id)
        else:
            state = next_state
            applied.append(event_id)
    return {"state": state, "applied": applied, "rejected": rejected}
""",
}

# Keys match current questions.yaml tests_file. v2 payloads equal fixture EXPECTED.
STRUCTURE = {
    "bank/tests/v2_architecture_hard_01.py": '{"status":"OK","kept":["c","a"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}',
    "bank/tests/v2_architecture_hard_02.py": '{"status":"OK","kept":["z","x"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":1}',
    "bank/tests/v2_architecture_hard_03.py": '{"status":"OK","kept":["q"],"trace":["DENY","TAKE","DUP","LIMIT"],"remaining":4}',
    "bank/tests/v2_architecture_hard_04.py": '{"status":"IMPOSSIBLE","conflict":["R0","R9"]}',
    "bank/tests/a_hard_05.py": (
        '{"atomic_write":"ONE_DB_TRANSACTION","publisher_retry":"RETRY_UNSENT",'
        '"consumer_key":"event_id","ack_order":"COMMIT_THEN_ACK",'
        '"dead_letter":"AFTER_MAX_RETRIES","replay":"IDEMPOTENT"}'
    ),
    "bank/tests/v2_architecture_extreme_01.py": (
        '{"actions":["APPLY","FUNDS","DUP","APPLY","APPLY","REFUND_LIMIT","APPLY"],'
        '"balance":7,"refundable_a":9,"seen":["a","b","c","d","e","f"]}'
    ),
    "bank/tests/a_extreme_02.py": (
        '{"read_mode":"OLD_FIRST","rollback_mode":"ROLL_BACK_APP_ONLY",'
        '"data_action":"BACKFILL_THEN_RETRY","compat_window":10,"lost_records":0}'
    ),
    "bank/tests/v2_architecture_extreme_03.py": (
        '{"actions":["ACCEPT","STALE","CONFLICT","ACCEPT","ACCEPT"],'
        '"token":10,"version":6,"value":50}'
    ),
    "bank/tests/a_extreme_04.py": (
        '{"relation":"CONCURRENT","resolution":"MANUAL_MERGE","value":"A+B",'
        '"vector":{"east":5,"west":4},"audit":"RETAIN_BOTH"}'
    ),
    "bank/tests/a_extreme_05.py": (
        '{"global_limit":240,"burst_capacity":60,"accepted_s1":300,"accepted_s2":60,'
        '"rejected_policy":"DROP_NO_REFUND","recovery":"RETRY_IDEMPOTENT"}'
    ),
    "bank/tests/v2_knowledge_easy_01.py": '{"address":"2001:db8::1:0:0:1"}',
    "bank/tests/v2_knowledge_medium_01.py": '{"service":"UNAVAILABLE","alias_allowed":false}',
    "bank/tests/v2_knowledge_hard_01.py": '{"relations":["NEWER","OLDER","UNDEFINED","EQUAL"],"add_250_10":4}',
    "bank/tests/v2_knowledge_hard_02.py": '{"ttl":240,"nxdomain_key":["QNAME","QCLASS"],"nodata_key":["QNAME","QTYPE","QCLASS"]}',
    "bank/tests/v2_knowledge_hard_03.py": '{"type":"TYPE65400","rdata":"\\\\# 3 00ff10","compress_names":false}',
    "bank/tests/v2_knowledge_hard_04.py": '{"base64url":"_w==","base32":"74======","pad_bits_zero":true}',
    "bank/tests/v2_knowledge_hard_05.py": '{"addresses":["2001:db8:0:1:2:3:4:5","2001::2:0:0:3:4","::"]}',
    "bank/tests/v2_knowledge_extreme_01.py": '{"after_first":4,"after_second":32771,"third_defined":false,"second_relation":"NEWER"}',
    "bank/tests/v2_knowledge_extreme_02.py": '{"x_hit":true,"y_hit":false,"x_remaining":30,"y_a_remaining":40}',
    "bank/tests/v2_knowledge_extreme_03.py": '{"first":["b","c"],"next":["a"],"weight_scope":"SAME_PRIORITY","target_alias":"FORBIDDEN"}',
    "bank/tests/v2_knowledge_extreme_04.py": '{"encodings":["MY======","MZXQ====","MZXW6==="],"alphabet_last":"7","bits_per_symbol":5}',
    "bank/tests/v2_knowledge_extreme_05.py": '{"lengths":[0,4],"hex_digits":[0,8],"empty_valid":true,"type_731":"TYPE731"}',
    "bank/tests/v2_reasoning_hard_01.py": '{"status":"OK","kept":["o","m"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":0}',
    "bank/tests/v2_reasoning_hard_02.py": '{"status":"OK","kept":["w","u"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}',
    "bank/tests/v2_reasoning_hard_03.py": '{"status":"IMPOSSIBLE","conflict":["R0","R9"]}',
    "bank/tests/v2_reasoning_hard_04.py": '{"status":"OK","kept":["x","z"],"trace":["TAKE","TAKE","LIMIT","DUP"],"remaining":1}',
    "bank/tests/r_hard_05.py": (
        '{"truth":[true,true,false],"liar_count":1,"consistent":true}'
    ),
    "bank/tests/r_hard_06.py": '{"swaps":8,"seven_enough":false}',
    "bank/tests/r_hard_07.py": '{"n":10,"left":1,"right":9}',
    "bank/tests/r_hard_08.py": '{"n":12,"smooth":0,"rough":12}',
    "bank/tests/r_hard_09.py": '{"h2022":1,"h12":2,"h25":4,"asl_fail":1.8}',
    "bank/tests/v2_reasoning_extreme_01.py": '{"base_indices":[1,3,4],"base_value":18,"changed_indices":[0,2],"changed_value":19,"delta":1}',
    "bank/tests/r_extreme_02.py": (
        '{"trace":[5,10,13,10,13],"final":13,"rolled_back":"ADD_3",'
        '"replayed":"ADD_3"}'
    ),
    "bank/tests/r_extreme_03.py": (
        '{"max_confidence":0.8,"decision":"CONFLICT","value":null,'
        '"witness":["E1","E2"]}'
    ),
    "bank/tests/r_extreme_04.py": (
        '{"x":2,"y":5,"cost":3,"optimal":true,"witness":"BIND_SUM"}'
    ),
    "bank/tests/v2_reasoning_extreme_05.py": (
        '{"path":["A","B","D"],"cost":5,"count":5,'
        '"changed_path":["A","B","E","D"],"changed_cost":5,"changed_count":3}'
    ),
}


def main() -> None:
    failed = 0
    for rel, code in PY.items():
        status, detail = run_python_sandbox(code, ROOT / rel)
        print(f"PY {rel}: {status} {detail}")
        if status != "pass":
            failed += 1
    for rel, payload in STRUCTURE.items():
        status, detail = run_python_sandbox("", ROOT / rel, payload=payload)
        print(f"STRUCT {rel}: {status} {detail}")
        if status != "pass":
            failed += 1
    if failed:
        raise SystemExit(failed)


if __name__ == "__main__":
    main()
