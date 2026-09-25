"""编程题 Python 参考实现。每个函数独立，可抽取为 solve 提交。"""


def merge_intervals(data):
    result = []
    for left, right in sorted(data["intervals"]):
        if left == right:
            continue
        if result and left <= result[-1][1]:
            result[-1][1] = max(result[-1][1], right)
        else:
            result.append([left, right])
    return {"intervals": result, "length": sum(b - a for a, b in result)}


def escaped_split(data):
    fields, current = [], []
    text = data["text"]
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            current.append(text[i + 1])
            i += 2
        elif text[i] == "|":
            fields.append("".join(current))
            current = []
            i += 1
        else:
            current.append(text[i])
            i += 1
    return fields + ["".join(current)]


def atomic_stock(data):
    stock = dict(data["initial"])
    seen, trace = set(), []
    for event in data["events"]:
        eid = event["id"]
        if eid in seen:
            trace.append("DUP")
            continue
        seen.add(eid)
        delta = {}
        for key, value in event["delta"]:
            delta[key] = delta.get(key, 0) + value
        if any(stock.get(key, 0) + value < 0 for key, value in delta.items()):
            trace.append("NEGATIVE")
            continue
        for key, value in delta.items():
            stock[key] = stock.get(key, 0) + value
        trace.append("OK")
    return {
        "stock": [[k, stock[k]] for k in sorted(stock) if stock[k] != 0],
        "trace": trace,
    }


def dependency_order(data):
    import heapq

    nodes = sorted(data["nodes"])
    graph = {v: set() for v in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for u, v in data["edges"]:
        if v not in graph[u]:
            graph[u].add(v)
            indegree[v] += 1
    ready = [v for v in nodes if indegree[v] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in graph[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                heapq.heappush(ready, v)
    if len(order) == len(nodes):
        return {"order": order, "cycle_nodes": []}
    # 上限 60 个节点，逐源可达性足够；避免将环的下游误报成环成员。
    cycle = []
    for start in nodes:
        todo, seen = list(graph[start]), set()
        while todo:
            u = todo.pop()
            if u in seen:
                continue
            seen.add(u)
            todo.extend(graph[u] - seen)
        if start in seen:
            cycle.append(start)
    return {"order": None, "cycle_nodes": cycle}


def weighted_schedule(data):
    from bisect import bisect_right

    jobs = sorted(data["jobs"], key=lambda x: (x["end"], x["start"], x["id"]))
    ends = [j["end"] for j in jobs]
    best = [(0, [])]
    for i, job in enumerate(jobs):
        index = bisect_right(ends, job["start"], 0, i)
        value, ids = best[index]
        take = (value + job["value"], ids + [job["id"]])
        skip = best[-1]
        best.append(min((take, skip), key=lambda x: (-x[0], len(x[1]), x[1])))
    return {"value": best[-1][0], "ids": best[-1][1]}


def snapshot_transactions(data):
    current = dict(data["initial"])
    last_write = dict.fromkeys(current, 0)
    version = 0
    active, reads, commits = {}, [], []
    for event in data["events"]:
        op, tx = event[:2]
        if op == "BEGIN":
            active[tx] = (version, dict(current), {})
        elif op == "GET":
            _, snapshot, writes = active[tx]
            key = event[2]
            reads.append([tx, key, writes.get(key, snapshot.get(key))])
        elif op == "SET":
            active[tx][2][event[2]] = event[3]
        else:
            snap_version, _, writes = active.pop(tx)
            conflict = any(last_write.get(k, 0) > snap_version for k in writes)
            if conflict:
                commits.append([tx, False, None])
            else:
                version += 1
                current.update(writes)
                for key in writes:
                    last_write[key] = version
                commits.append([tx, True, version])
    return {
        "reads": reads,
        "commits": commits,
        "final": [[k, current[k]] for k in sorted(current)],
    }


def dynamic_connectivity(data):
    n, events = data["n"], data["events"]
    count, start, intervals = {}, {}, []
    for t, (op, u, v) in enumerate(events):
        edge = tuple(sorted((u, v)))
        if op == "ADD":
            if count.get(edge, 0) == 0:
                start[edge] = t
            count[edge] = count.get(edge, 0) + 1
        elif op == "REMOVE" and count.get(edge, 0):
            count[edge] -= 1
            if count[edge] == 0:
                intervals.append((start.pop(edge), t, edge))
    total = len(events)
    for edge, begin in start.items():
        intervals.append((begin, total, edge))
    if not total:
        return []
    tree = [[] for _ in range(4 * total)]

    def put(node, left, right, begin, end, edge):
        if begin >= right or end <= left:
            return
        if begin <= left and right <= end:
            tree[node].append(edge)
            return
        mid = (left + right) // 2
        put(node * 2, left, mid, begin, end, edge)
        put(node * 2 + 1, mid, right, begin, end, edge)

    for begin, end, edge in intervals:
        put(1, 0, total, begin, end, edge)
    parent, size, history, answer = list(range(n)), [1] * n, [], []

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def visit(node, left, right):
        checkpoint = len(history)
        for u, v in tree[node]:
            a, b = find(u), find(v)
            if a == b:
                continue
            if size[a] < size[b]:
                a, b = b, a
            history.append((b, a, size[a]))
            parent[b] = a
            size[a] += size[b]
        if right - left == 1:
            op, u, v = events[left]
            if op == "ASK":
                answer.append(find(u) == find(v))
        else:
            mid = (left + right) // 2
            visit(node * 2, left, mid)
            visit(node * 2 + 1, mid, right)
        while len(history) > checkpoint:
            b, a, old_size = history.pop()
            parent[b], size[a] = b, old_size

    visit(1, 0, total)
    return answer


def register_machine(data):
    import re

    integer = re.compile(r"[+-]?[0-9]+\Z")
    identifier = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
    low, high = -(2**31), 2**31 - 1
    labels, program = {}, []
    arity = {
        "SET": 3,
        "ADD": 3,
        "MUL": 3,
        "MOD": 3,
        "JZ": 3,
        "JNZ": 3,
        "JMP": 2,
        "HALT": 1,
    }

    def operand(token):
        return token in {"A", "B", "C"} or bool(
            integer.fullmatch(token) and low <= int(token) <= high
        )

    for line in data["src"].splitlines():
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        op = parts[0]
        if op == "LABEL":
            if (
                len(parts) != 2
                or not identifier.fullmatch(parts[1])
                or parts[1] in labels
            ):
                return {"status": "ERR", "steps": 0}
            labels[parts[1]] = len(program)
            continue
        if op not in arity or len(parts) != arity[op]:
            return {"status": "ERR", "steps": 0}
        if op in {"SET", "ADD", "MUL", "MOD"} and (
            parts[1] not in {"A", "B", "C"} or not operand(parts[2])
        ):
            return {"status": "ERR", "steps": 0}
        if op in {"JZ", "JNZ"} and parts[1] not in {"A", "B", "C"}:
            return {"status": "ERR", "steps": 0}
        program.append(parts)
    for parts in program:
        if parts[0] in {"JMP", "JZ", "JNZ"} and parts[-1] not in labels:
            return {"status": "ERR", "steps": 0}
    regs = dict.fromkeys("ABC", 0)
    pc = steps = 0
    while pc < len(program):
        if steps == data["limit"]:
            return {"status": "TIMEOUT", "steps": steps}
        parts = program[pc]
        op = parts[0]
        steps += 1
        if op == "HALT":
            break
        if op in {"JMP", "JZ", "JNZ"}:
            jump = (
                op == "JMP"
                or (op == "JZ" and regs[parts[1]] == 0)
                or (op == "JNZ" and regs[parts[1]] != 0)
            )
            pc = labels[parts[-1]] if jump else pc + 1
            continue
        x, token = parts[1:]
        value = regs[token] if token in regs else int(token)
        if op == "SET":
            result = value
        elif op == "ADD":
            result = regs[x] + value
        elif op == "MUL":
            result = regs[x] * value
        else:
            if value == 0:
                return {"status": "DIV0", "steps": steps}
            result = regs[x] % value
        if not low <= result <= high:
            return {"status": "OVERFLOW", "steps": steps}
        regs[x] = result
        pc += 1
    return {"status": "OK", "value": regs["A"], "steps": steps}
