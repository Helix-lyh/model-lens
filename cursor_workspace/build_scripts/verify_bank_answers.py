"""Verify Python bank tests and structure tests against known-good answers."""

from __future__ import annotations

from src.bank import repo_root
from src.grade import run_sandbox

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
        candidate = (value, -weight, [-i for i in chosen])
        current = (best[0], -best[1], [-i for i in best[2]])
        if candidate > current:
            best = (value, weight, chosen)
    return {"value": best[0], "weight": best[1], "indices": best[2]}
""",
    "bank/tests/b16_mvcc.py": """
def apply_transactions(initial, txns):
    state = dict(initial)
    statuses = {}
    versions = {key: 0 for key in state}
    for txn in sorted(txns, key=lambda x: x["commit"]):
        if any(versions.get(key, 0) > txn["begin"] for key in txn["writes"]):
            statuses[txn["id"]] = "ABORT"
            continue
        statuses[txn["id"]] = "COMMIT"
        for key, value in txn["writes"].items():
            state[key] = value
            versions[key] = txn["commit"]
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
        ("DELIVERED", "REFUND"): "REFUNDED",
        ("CREATED", "CANCEL"): "CANCELLED",
        ("PAID", "CANCEL"): "CANCELLED",
        ("SHIPPED", "CANCEL"): "CANCELLED",
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

STRUCTURE = {
    "bank/tests/c09_lines6.py": "[[v2]]\nsgnl\nsgnl-sgnl\n9\nlngs\n[[end]]",
    "bank/tests/c10_meta.py": '{"data": ["0", 0, false, null], "meta": {"v": 1e2, "k k": {}}}',
    "bank/tests/c11_logic_grid.py": (
        '{"A": {"floor": 2, "drink": "茶"}, "B": {"floor": 3, "drink": "咖啡"},'
        ' "C": {"floor": 1, "drink": "可乐"}}'
    ),
    "bank/tests/a_hard_01.py": (
        '{"failure_code":"OFFSET_SCAN","index_columns":["created_at","id"],'
        '"pagination":"KEYSET","cursor_predicate":"(created_at,id)<(cursor_time,cursor_id)",'
        '"rows_scanned":20}'
    ),
    "bank/tests/a_hard_02.py": (
        '{"auth":"SIGNED_URL_900S","transport":"DIRECT_OBJECT_STORAGE",'
        '"parts":{"size_mib":16},"scan":"QUARANTINED_TO_CLEAN_OR_REJECTED",'
        '"publish":"CLEAN_ONLY"}'
    ),
    "bank/tests/a_hard_03.py": (
        '{"redis_owner":"B","a_renew":"REJECT","a_write":"REJECT_FENCING",'
        '"b_write":"ACCEPT","brain_split":true,"required_guard":"COMPARE_AND_SET_TOKEN"}'
    ),
    "bank/tests/a_hard_04.py": (
        '{"events":["APPLY_SUCCESS","IGNORE_DUPLICATE","APPLY_REFUND","RECONCILE_GAP"],'
        '"final_state":"PARTIALLY_REFUNDED","ledger_amount":60,"missing_seq":[5],'
        '"idempotent_key":"payment_id+seq"}'
    ),
    "bank/tests/a_hard_05.py": (
        '{"atomic_write":"ONE_DB_TRANSACTION","publisher_retry":"RETRY_UNSENT",'
        '"consumer_key":"event_id","ack_order":"COMMIT_THEN_ACK",'
        '"dead_letter":"AFTER_MAX_RETRIES","replay":"IDEMPOTENT"}'
    ),
    "bank/tests/a_extreme_01.py": (
        '{"actions":["APPLY","APPLY","REJECT_DUP","APPLY","FLAG"],'
        '"balance":120,"accepted_seq":[1,2,3],"flags":1}'
    ),
    "bank/tests/a_extreme_02.py": (
        '{"read_mode":"OLD_FIRST","rollback_mode":"ROLL_BACK_APP_ONLY",'
        '"data_action":"BACKFILL_THEN_RETRY","compat_window":10,"lost_records":0}'
    ),
    "bank/tests/a_extreme_03.py": (
        '{"a_result":"REJECT_STALE","b_result":"ACCEPT","stored_token":12,'
        '"stored_version":5,"lease_rule":"TOKEN_CHECK_AT_STORAGE"}'
    ),
    "bank/tests/a_extreme_04.py": (
        '{"relation":"CONCURRENT","resolution":"MANUAL_MERGE","value":"A+B",'
        '"vector":{"east":5,"west":4},"audit":"RETAIN_BOTH"}'
    ),
    "bank/tests/a_extreme_05.py": (
        '{"global_limit":240,"burst_capacity":60,"accepted_s1":300,"accepted_s2":60,'
        '"rejected_policy":"DROP_NO_REFUND","recovery":"RETRY_IDEMPOTENT"}'
    ),
    "bank/tests/k_hard_01.py": (
        '{"reading_mA":2.4,"upper_mA":2.52,"risk":"HIGH","unit":"mA"}'
    ),
    "bank/tests/k_hard_02.py": (
        '{"chosen_source":"lab","chosen_value":18,"discarded":["R2","R3"]}'
    ),
    "bank/tests/k_hard_03.py": (
        '{"after_discount":770.0,"tax_base":790.0,"tax":63.2,"total":853.2}'
    ),
    "bank/tests/k_hard_04.py": (
        '{"labels":["AMBER","GREEN","RED","GREEN"],"red_count":1,"green_count":2}'
    ),
    "bank/tests/k_hard_05.py": (
        '{"old_threshold":11,"new_threshold":15,"old_action":"HOLD",'
        '"new_action":"RESTOCK"}'
    ),
    "bank/tests/k_extreme_01.py": (
        '{"load_kwh":2.1,"battery_kwh":2.4,"days_supported":1.029,'
        '"status":"ONE_DAY"}'
    ),
    "bank/tests/k_extreme_02.py": (
        '{"before":"B","after":"NONE","before_reason":"B_MEETS_RULE",'
        '"after_reason":"NO_QUALIFIED_SUPPLIER"}'
    ),
    "bank/tests/k_extreme_03.py": (
        '{"fail_weight":0.9,"pass_weight":1.0,"decision":"PASS","margin":0.1}'
    ),
    "bank/tests/k_extreme_04.py": (
        '{"winning_rule":"R3","decision":"REVIEW",'
        '"suppressed_rules":["R2","R1"],"evidence_count":1}'
    ),
    "bank/tests/k_extreme_05.py": (
        '{"before_total":1029.0,"before_decision":"REVIEW","after_total":999.6,'
        '"after_decision":"ACCEPT","delta":-29.4}'
    ),
    "bank/tests/r_hard_01.py": (
        '{"order":["A","C","B","D"],"slot_A":1,"slot_D":4,"feasible":true}'
    ),
    "bank/tests/r_hard_02.py": (
        '{"assignment":{"A":1,"B":1,"C":2,"D":2},'
        '"loads":{"1":7,"2":7},"minimum_resources":2,"feasible":true}'
    ),
    "bank/tests/r_hard_03.py": (
        '{"counterexample":2,"square":4,"divisible_by_4":false,"verdict":"FALSE"}'
    ),
    "bank/tests/r_hard_04.py": (
        '{"path":["A","C","E","D"],"cost":7,"hops":3,"unique":true}'
    ),
    "bank/tests/r_hard_05.py": (
        '{"truth":[true,true,false],"liar_count":1,"consistent":true}'
    ),
    "bank/tests/r_extreme_01.py": (
        '{"base_indices":[0,2],"base_value":17,"counterfactual_indices":[0,2],'
        '"counterfactual_value":17,"delta":0}'
    ),
    "bank/tests/r_extreme_02.py": (
        '{"trace":[5,10,13,10,13],"final":13,"rolled_back":"ADD_3",'
        '"replayed":"ADD_3"}'
    ),
    "bank/tests/r_extreme_03.py": (
        '{"max_confidence":0.8,"decision":"CONFLICT","value":null,'
        '"witness":["E1","E2"]}'
    ),
    "bank/tests/r_extreme_04.py": (
        '{"x":2,"y":5,"cost":3,"optimal":true,"witness":"x+y=7"}'
    ),
    "bank/tests/r_extreme_05.py": (
        '{"base_indices":[0,1,3],"base_value":17,"changed_indices":[0,1,3],'
        '"changed_value":17,"difference":0}'
    ),
}


def main() -> None:
    failed = 0
    for rel, code in PY.items():
        status, detail = run_sandbox(code, ROOT / rel)
        print(f"PY {rel}: {status} {detail}")
        if status != "pass":
            failed += 1
    for rel, payload in STRUCTURE.items():
        status, detail = run_sandbox("", ROOT / rel, payload=payload)
        print(f"STRUCT {rel}: {status} {detail}")
        if status != "pass":
            failed += 1
    if failed:
        raise SystemExit(failed)


if __name__ == "__main__":
    main()
