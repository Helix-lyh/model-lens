"""固定种子产生审核用例。每题五组，每组四个独立计分检查，每检查可含多例。"""

from copy import deepcopy
from dataclasses import dataclass
from random import Random

from . import references
from .oracles import bfs_connectivity, brute_weighted_schedule


@dataclass
class Case:
    data: dict
    expected: object


def _case(fn, data, expected=...):
    value = fn(deepcopy(data))
    if expected is not ...:
        assert value == expected, (fn.__name__, data, value, expected)
    return Case(data, value)


def _independent_intervals(data):
    points = sorted({x for pair in data["intervals"] for x in pair})
    segments = [
        (a, b)
        for a, b in zip(points, points[1:])
        if any(l <= a and b <= r for l, r in data["intervals"])
    ]
    result = []
    for a, b in segments:
        if result and result[-1][1] == a:
            result[-1][1] = b
        else:
            result.append([a, b])
    return {"intervals": result, "length": sum(b - a for a, b in result)}


def _independent_split(data):
    out = [""]
    escaping = False
    for ch in data["text"]:
        if escaping:
            out[-1] += ch
            escaping = False
        elif ch == "\\":
            escaping = True
        elif ch == "|":
            out.append("")
        else:
            out[-1] += ch
    if escaping:
        out[-1] += "\\"
    return out


def _independent_stock(data):
    stock = dict(data["initial"])
    trace = []
    history = []
    for event in data["events"]:
        if event["id"] in history:
            trace.append("DUP")
            continue
        history.append(event["id"])
        keys = set(stock) | {k for k, _ in event["delta"]}
        proposed = {
            k: stock.get(k, 0) + sum(v for sku, v in event["delta"] if sku == k)
            for k in keys
        }
        if min(proposed.values(), default=0) < 0:
            trace.append("NEGATIVE")
        else:
            stock = proposed
            trace.append("OK")
    return {"stock": [[k, stock[k]] for k in sorted(stock) if stock[k]], "trace": trace}


def _independent_graph(data):
    nodes = sorted(data["nodes"])
    index = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    reach = [[False] * n for _ in nodes]
    for a, b in data["edges"]:
        reach[index[a]][index[b]] = True
    for k in range(n):
        for i in range(n):
            for j in range(n):
                reach[i][j] = reach[i][j] or reach[i][k] and reach[k][j]
    cycles = [nodes[i] for i in range(n) if reach[i][i]]
    if cycles:
        return {"order": None, "cycle_nodes": cycles}
    left = set(nodes)
    order = []
    while left:
        chosen = min(
            v for v in left if not any(a in left and b == v for a, b in data["edges"])
        )
        order.append(chosen)
        left.remove(chosen)
    return {"order": order, "cycle_nodes": []}


def _independent_transactions(data):
    # 用每个 key 的提交历史查找快照值，与复制整张快照的参考实现不同。
    history = {k: [(0, v)] for k, v in data["initial"].items()}
    active = {}
    version = 0
    reads = []
    commits = []
    for event in data["events"]:
        op, tx = event[:2]
        if op == "BEGIN":
            active[tx] = {"at": version, "writes": {}}
        elif op == "GET":
            key = event[2]
            state = active[tx]
            visible = [v for ver, v in history.get(key, []) if ver <= state["at"]]
            reads.append(
                [tx, key, state["writes"].get(key, visible[-1] if visible else None)]
            )
        elif op == "SET":
            active[tx]["writes"][event[2]] = event[3]
        else:
            state = active.pop(tx)
            conflict = any(
                any(ver > state["at"] for ver, _ in history.get(k, []))
                for k in state["writes"]
            )
            if conflict:
                commits.append([tx, False, None])
                continue
            version += 1
            for key, value in state["writes"].items():
                history.setdefault(key, []).append((version, value))
            commits.append([tx, True, version])
    return {
        "reads": reads,
        "commits": commits,
        "final": [[k, history[k][-1][1]] for k in sorted(history)],
    }


def _batches(fn, groups, independent):
    return [
        [[_case(fn, data, independent(data)) for data in batch] for batch in group]
        for group in groups
    ]


def coding_cases(item_id):
    rng = Random(20260925)
    if item_id == "P-E-01":
        groups = [
            [[], [[1, 1]], [[0, 0], [2, 2]], [[3, 3], [-1, -1], [0, 0]]],
            [
                [[1, 2], [2, 3]],
                [[3, 5], [0, 3]],
                [[-3, 0], [0, 2], [2, 4]],
                [[1, 2], [3, 4]],
            ],
            [
                [[1, 5], [2, 3]],
                [[1, 4], [3, 7]],
                [[0, 10], [2, 8], [3, 5]],
                [[1, 2], [1, 2], [1, 2]],
            ],
            [
                [[8, 9], [1, 2], [4, 5]],
                [[3, 4], [2, 3], [1, 2]],
                [[-5, -2], [-4, -1]],
                [[100, 200], [-200, -100], [0, 1]],
            ],
            [
                [[rng.randrange(-20, 20), rng.randrange(20, 40)] for _ in range(30)]
                for _ in range(4)
            ],
        ]
        nested = [[[{"intervals": x}] for x in g] for g in groups]
        return _batches(references.merge_intervals, nested, _independent_intervals)
    if item_id == "P-E-02":
        groups = [
            ["", "|", "||", "a||b|"],
            [r"a\|b", r"\|", r"a\|b|c", r"\||\|"],
            [r"\\", r"\\|x", r"\\\|", r"a\\b|c"],
            ["\\", "a\\", "a|\\", "\\\\\\"],
            ["".join(rng.choice("ab|\\ ?") for _ in range(200)) for _ in range(4)],
        ]
        return _batches(
            references.escaped_split,
            [[[{"text": x}] for x in g] for g in groups],
            _independent_split,
        )
    if item_id == "P-N-01":

        def data(initial, events):
            return {
                "initial": initial,
                "events": [{"id": eid, "delta": delta} for eid, delta in events],
            }

        groups = [
            [
                data({}, []),
                data({"a": 2}, [("x", [["a", 3]])]),
                data({}, [("x", [["constructor", 2], ["toString", 1]])]),
                data({"a": 0}, [("x", [])]),
            ],
            [
                data({"a": 1, "b": 2}, [("x", [["a", 2], ["b", -3]])]),
                data({}, [("x", [["a", -1]])]),
                data({"a": 1}, [("x", [["a", -1]])]),
                data({"a": 1}, [("x", [["a", -2]]), ("y", [["a", -1]])]),
            ],
            [
                data({}, [("x", [["a", -1]]), ("x", [["a", 5]])]),
                data({}, [("x", []), ("x", [["a", 2]])]),
                data({}, [("x", [["a", 2]]), ("x", [["a", 2]])]),
                data(
                    {"a": 3},
                    [("x", [["a", -5]]), ("y", [["a", 4]]), ("x", [["a", -1]])],
                ),
            ],
            [
                data({"a": 2}, [("x", [["a", -3], ["a", 1]])]),
                data({}, [("x", [["a", -2], ["a", 2]])]),
                data({"a": 2}, [("x", [["a", 2], ["a", -5]])]),
                data({"a": 1, "b": 1}, [("x", [["a", -2], ["b", 2], ["a", 1]])]),
            ],
            [
                data(
                    {"a": 3, "b": 2},
                    [
                        (
                            str(rng.randrange(10)),
                            [
                                [rng.choice("abc"), rng.randrange(-3, 4)]
                                for _ in range(4)
                            ],
                        )
                        for _ in range(40)
                    ],
                )
                for _ in range(4)
            ],
        ]
        return _batches(
            references.atomic_stock,
            [[[x] for x in g] for g in groups],
            _independent_stock,
        )
    if item_id == "P-N-02":

        def d(nodes, edges):
            return {"nodes": list(nodes), "edges": [list(e) for e in edges]}

        groups = [
            [
                d("", []),
                d("a", []),
                d("abc", ["ab", "bc"]),
                d("abcd", ["ab", "ac", "bd", "cd"]),
            ],
            [
                d("cba", []),
                d("abcd", ["ac", "bd"]),
                d("abc", ["ac", "ac"]),
                d("abcdef", ["cf", "be", "ad"]),
            ],
            [
                d("a", ["aa"]),
                d("ab", ["ab", "ba"]),
                d("abc", ["ab", "bc", "ca"]),
                d("abcd", ["ab", "ba", "cd", "dc"]),
            ],
            [
                d("abc", ["ab", "ba", "bc"]),
                d("abcd", ["aa", "ab", "bc", "cd"]),
                d("abcd", ["ab", "bc", "cb", "cd"]),
                d("abcde", ["ab", "ba", "bc", "cd", "de"]),
            ],
            [
                d(
                    "abcdef",
                    [(a, b) for a in "abcdef" for b in "abcdef" if rng.random() < 0.18],
                )
                for _ in range(4)
            ],
        ]
        return _batches(
            references.dependency_order,
            [[[x] for x in g] for g in groups],
            _independent_graph,
        )
    if item_id == "P-H-01":

        def d(rows):
            return {
                "jobs": [dict(zip(("id", "start", "end", "value"), r)) for r in rows]
            }

        groups = [
            [d([]), d([("a", 0, 1, 3)]), d([("a", 0, 1, -1)]), d([("a", 0, 1, 0)])],
            [
                d([("a", 0, 2, 2), ("b", 2, 4, 3)]),
                d([("a", 0, 3, 3), ("b", 2, 4, 5)]),
                d([("a", 0, 6, 5), ("b", 1, 2, 4), ("c", 3, 5, 4)]),
                d([("a", 0, 2, -1), ("b", 2, 3, 4)]),
            ],
            [
                d([("a", 0, 2, 4), ("b", 2, 4, 4), ("c", 0, 4, 8)]),
                d([("a", 0, 1, 0), ("b", 1, 2, 2)]),
                d([("a", 0, 2, 4), ("b", 0, 1, 2), ("c", 1, 2, 2)]),
                d([("a", 0, 1, 1), ("b", 1, 2, 1), ("z", 0, 2, 2), ("c", 2, 3, 1)]),
            ],
            [
                d([("b", 0, 2, 3), ("a", 0, 2, 3)]),
                d([("z", 0, 1, 2), ("a", 1, 2, 2), ("b", 0, 1, 2), ("c", 1, 2, 2)]),
                d([("a", 2, 4, 2), ("b", 0, 2, 2), ("c", 0, 4, 3)]),
                d([("a", 0, 3, 3), ("aa", 0, 3, 3), ("b", 3, 4, 1)]),
            ],
        ]
        result = _batches(
            references.weighted_schedule,
            [[[x] for x in g] for g in groups],
            brute_weighted_schedule,
        )
        scale = []
        for batch in range(4):
            samples = []
            for _ in range(20):
                rows = []
                for i in range(10):
                    start = rng.randrange(12)
                    rows.append(
                        (
                            f"j{i:02}",
                            start,
                            start + rng.randrange(1, 6),
                            rng.randrange(-3, 10),
                        )
                    )
                x = d(rows)
                samples.append(
                    _case(references.weighted_schedule, x, brute_weighted_schedule(x))
                )
            count = 2000
            x = d([(f"j{i:04}", 2 * i, 2 * i + 1, 1) for i in range(count)])
            samples.append(
                _case(
                    references.weighted_schedule,
                    x,
                    {"value": count, "ids": [f"j{i:04}" for i in range(count)]},
                )
            )
            scale.append(samples)
        return result + [scale]
    if item_id == "P-H-02":

        def d(events, initial=None):
            return {"initial": initial or {}, "events": [list(e) for e in events]}

        B = lambda t: ("BEGIN", t)
        G = lambda t, k: ("GET", t, k)
        S = lambda t, k, v: ("SET", t, k, v)
        C = lambda t: ("COMMIT", t)
        groups = [
            [
                d([B("a"), G("a", "x")]),
                d([B("a"), B("b"), S("a", "x", 2), C("a"), G("b", "x")], {"x": 1}),
                d([B("a"), S("a", "x", 2), B("b"), G("b", "x")], {"x": 1}),
                d([B("a"), C("a"), B("b"), G("b", "x")], {"x": 0}),
            ],
            [
                d([B("a"), S("a", "x", 2), G("a", "x")]),
                d([B("a"), S("a", "x", 2), S("a", "x", 3), G("a", "x"), C("a")]),
                d([B("a"), S("a", "x", 0), G("a", "x"), C("a")]),
                d(
                    [
                        B("a"),
                        B("b"),
                        S("a", "x", 2),
                        S("b", "x", 3),
                        G("a", "x"),
                        G("b", "x"),
                    ]
                ),
            ],
            [
                d([B("a"), B("b"), S("a", "x", 1), C("a"), S("b", "x", 2), C("b")]),
                d(
                    [B("a"), B("b"), S("a", "x", 1), C("a"), S("b", "x", 1), C("b")],
                    {"x": 1},
                ),
                d(
                    [
                        B("a"),
                        B("b"),
                        S("a", "x", 1),
                        C("a"),
                        S("b", "y", 2),
                        S("b", "x", 3),
                        C("b"),
                    ]
                ),
                d([B("a"), B("b"), S("a", "x", 1), S("b", "y", 2), C("a"), C("b")]),
            ],
            [
                d([B("a"), C("a")]),
                d([B("a"), B("b"), C("b"), C("a")]),
                d(
                    [
                        B("a"),
                        B("b"),
                        S("a", "x", 1),
                        C("a"),
                        S("b", "x", 2),
                        C("b"),
                        B("c"),
                        C("c"),
                    ]
                ),
                d([B("a"), S("a", "x", 1), C("a"), B("b"), S("b", "x", 2), C("b")]),
            ],
            [
                d(
                    [
                        B("a"),
                        B("b"),
                        G("a", "y"),
                        G("b", "x"),
                        S("a", "x", 0),
                        S("b", "y", 0),
                        C("a"),
                        C("b"),
                    ],
                    {"x": 1, "y": 1},
                ),
                d([B("a"), S("a", "x", 9)], {"x": 1}),
                d(
                    [B("a"), B("b"), G("b", "x"), S("a", "x", 3), C("a"), C("b")],
                    {"x": 1},
                ),
                d(
                    [
                        B("a"),
                        B("b"),
                        S("a", "x", 1),
                        C("a"),
                        G("b", "x"),
                        B("c"),
                        G("c", "x"),
                    ]
                ),
            ],
        ]
        return _batches(
            references.snapshot_transactions,
            [[[x] for x in g] for g in groups],
            _independent_transactions,
        )
    if item_id == "P-X-01":

        def d(events, n=5):
            return {"n": n, "events": [list(e) for e in events]}

        groups = [
            [
                d([]),
                d([("ASK", 0, 0)]),
                d([("ASK", 0, 1)]),
                d([("ADD", 0, 1), ("ADD", 1, 2), ("ASK", 0, 2)]),
            ],
            [
                d([("ADD", 0, 1), ("ADD", 1, 0), ("REMOVE", 0, 1), ("ASK", 0, 1)]),
                d([("ADD", 0, 1), ("REMOVE", 1, 0), ("ASK", 0, 1)]),
                d([("ADD", 0, 0), ("REMOVE", 0, 0), ("ASK", 0, 0)]),
                d([("REMOVE", 0, 1), ("ADD", 0, 1), ("ASK", 0, 1)]),
            ],
            [
                d([("ADD", 0, 1), ("REMOVE", 0, 1), ("ASK", 0, 1)]),
                d(
                    [
                        ("ADD", 0, 1),
                        ("ADD", 1, 2),
                        ("ADD", 0, 2),
                        ("REMOVE", 0, 2),
                        ("ASK", 0, 2),
                    ]
                ),
                d([("ADD", 0, 1), ("ADD", 1, 2), ("REMOVE", 1, 2), ("ASK", 0, 2)]),
                d(
                    [
                        ("ADD", 0, 1),
                        ("ADD", 0, 1),
                        ("REMOVE", 0, 1),
                        ("REMOVE", 0, 1),
                        ("ASK", 0, 1),
                    ]
                ),
            ],
            [
                d(
                    [
                        (
                            rng.choice(("ADD", "REMOVE", "ASK")),
                            rng.randrange(5),
                            rng.randrange(5),
                        )
                        for _ in range(80)
                    ]
                )
                for _ in range(4)
            ],
        ]
        result = _batches(
            references.dynamic_connectivity,
            [[[x] for x in g] for g in groups],
            bfs_connectivity,
        )
        scale = []
        for offset in range(4):
            n = 20000
            events = [("ADD", i, i + 1) for i in range(n - 1)]
            expected = []
            # 39999 个事件。完整链的查询会使每次 BFS 扫描接近 20000 节点。
            for i in range(5000):
                cut = (i * 37 + offset) % (n - 1)
                events.extend(
                    [
                        ("REMOVE", cut, cut + 1),
                        ("ASK", 0, n - 1),
                        ("ADD", cut, cut + 1),
                        ("ASK", 0, n - 1),
                    ]
                )
                expected.extend([False, True])
            scale.append(
                [_case(references.dynamic_connectivity, d(events, n), expected)]
            )
        return result + [scale]
    if item_id == "P-X-02":

        def ok(value, steps):
            return {"status": "OK", "value": value, "steps": steps}

        def err(status, steps=0):
            return {"status": status, "steps": steps}

        groups = [
            [
                ("SET A 3\nSET B 4\nADD A B\nHALT", 10, ok(7, 4)),
                ("SET A -7\nMOD A 3", 10, ok(2, 2)),
                ("SET A 7\nMOD A -3", 10, ok(-2, 2)),
                ("SET A -7\nMOD A -3", 10, ok(-1, 2)),
            ],
            [
                ("HALT\nSET D 1", 10, err("ERR")),
                ("JZ A missing\nHALT", 10, err("ERR")),
                ("SET A 1\nJZ A missing", 10, err("ERR")),
                ("HALT\nLABEL x\nLABEL x", 10, err("ERR")),
            ],
            [
                ("JMP end\nSET A 9\nLABEL end", 1, ok(0, 1)),
                ("SET A 3\nLABEL l\nADD A -1\nJNZ A l", 7, ok(0, 7)),
                ("LABEL X\nJMP x", 10, err("ERR")),
                ("# comment\nLABEL start\nLABEL next\nHALT", 1, ok(0, 1)),
            ],
            [
                ("SET A 2147483647\nADD A 1", 10, err("OVERFLOW", 2)),
                ("SET A -2147483648\nMUL A -1", 10, err("OVERFLOW", 2)),
                ("MOD A 0", 10, err("DIV0", 1)),
                ("MOD A 0\nBOGUS", 0, err("ERR")),
            ],
            [
                ("", 0, ok(0, 0)),
                ("HALT", 0, err("TIMEOUT")),
                ("SET A 1\nHALT", 1, err("TIMEOUT", 1)),
                ("SET A 1\nHALT", 2, ok(1, 2)),
            ],
        ]
        result = [
            [
                [
                    _case(
                        references.register_machine,
                        {"src": src, "limit": limit},
                        expected,
                    )
                ]
                for src, limit, expected in g
            ]
            for g in groups
        ]
        extras = [
            (0, 0, "SET A +0003\nMUL A A", 10, ok(9, 2)),
            (1, 0, "HALT extra", 10, err("ERR")),
            (1, 1, "SET A 2147483648", 10, err("ERR")),
            (1, 2, "LABEL 2bad\nHALT", 10, err("ERR")),
            (1, 3, "set A 1", 10, err("ERR")),
            (2, 0, "SET A 2\nJNZ A end\nSET A 9\nLABEL end", 2, ok(2, 2)),
            (3, 0, "SET A 2147483647\nMUL A 2147483647", 10, err("OVERFLOW", 2)),
            (3, 1, "SET A -2147483648\nMOD A -1", 10, ok(0, 2)),
            (3, 2, "MOD A 0", 0, err("TIMEOUT")),
            (4, 0, "LABEL end", 0, ok(0, 0)),
            (4, 1, "LABEL loop\nJMP loop", 10000, err("TIMEOUT", 10000)),
            (4, 2, "SET A 1", 1, ok(1, 1)),
            (4, 3, "SET A 1\nHALT\nMOD A 0", 2, ok(1, 2)),
        ]
        for g, p, src, limit, expected in extras:
            result[g][p].append(
                _case(
                    references.register_machine, {"src": src, "limit": limit}, expected
                )
            )
        return result
    raise KeyError(item_id)
