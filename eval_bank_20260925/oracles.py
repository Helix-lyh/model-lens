"""离线复核参考答案；不会向待测模型发送此文件。"""

from collections import Counter, deque
from functools import lru_cache
from itertools import combinations, permutations, product
from fractions import Fraction


def coins():
    reachable = {
        5 * a + 8 * b + 11 * c for a in range(41) for b in range(26) for c in range(19)
    }
    residues = [min(x for x in reachable if x % 5 == r) for r in range(5)]
    impossible = [x for x in range(1, 51) if x not in reachable]
    # 独立逐金额递推，不读取上面的集合。
    dp = [True] + [False] * 200
    for x in range(1, 201):
        dp[x] = any(x >= c and dp[x - c] for c in (5, 8, 11))
    assert impossible == [x for x in range(1, 51) if not dp[x]]
    return {
        "residue_min": residues,
        "impossible": impossible,
        "largest": max(impossible),
        "count": len(impossible),
    }


def urn():
    # U: 3红1蓝；V: 1红3蓝。先验 U=1/3,V=2/3。不放回抽两球后报告至少一红。
    possible = [[i, j] for i, j in combinations(range(4), 2)]
    likelihood = []
    joint = Fraction(0)
    for red, prior in [(3, Fraction(1, 3)), (1, Fraction(2, 3))]:
        accepted = [p for p in possible if any(x < red for x in p)]
        likelihood.append(Fraction(len(accepted), 6))
        joint += prior * Fraction(sum(all(x < red for x in p) for p in accepted), 6)
    evidence = sum(p * l for p, l in zip((Fraction(1, 3), Fraction(2, 3)), likelihood))
    posterior = Fraction(1, 3) * likelihood[0] / evidence
    pair = lambda x: [x.numerator, x.denominator]
    assert posterior == Fraction(1, 2) and joint / evidence == Fraction(1, 4)
    return {
        "likelihood_u": pair(likelihood[0]),
        "likelihood_v": pair(likelihood[1]),
        "posterior_u": pair(posterior),
        "both_red": pair(joint / evidence),
    }


def glove_fixed():
    left, right = (3, 5, 4), (4, 2, 6)
    frontier = []
    for count in range(sum(left) + 1):
        frontier.append(
            max(
                sum(right[i] for i in range(3) if not mask >> i & 1)
                for mask in range(8)
                if sum(left[i] for i in range(3) if mask >> i & 1) >= count
            )
        )
    bad = set()
    for a in product(*(range(x + 1) for x in left)):
        for b in product(*(range(x + 1) for x in right)):
            if not any(x and y for x, y in zip(a, b)):
                bad.add((sum(a), sum(b)))
    assert frontier == [
        max(r for l, r in bad if l == count) for count in range(sum(left) + 1)
    ]
    candidates = [
        (l + r, l, r) for l in range(13) for r in range(13) if (l, r) not in bad
    ]
    minimum = min(x[0] for x in candidates)
    allocations = [[l, r] for total, l, r in candidates if total == minimum]
    return {
        "frontier": frontier,
        "minimum": minimum,
        "allocations": allocations,
        "counterexample": {"left": [0, 5, 0], "right": [4, 0, 1]},
    }


def restricted_permutations():
    def enumerate_n(n):
        even = odd = 0
        for p in permutations(range(1, n + 1)):
            if p[0] >= p[-1] or any(
                v == i + 1 or (i < n - 1 and v == i + 2) for i, v in enumerate(p)
            ):
                continue
            inversions = sum(p[i] > p[j] for i in range(n) for j in range(i + 1, n))
            if inversions % 2:
                odd += 1
            else:
                even += 1
        return even, odd

    @lru_cache(None)
    def dp(n, mask, first, parity):
        i = mask.bit_count()
        if i == n:
            return (int(parity == 0), int(parity == 1))
        counts = [0, 0]
        for v in range(n):
            if (
                mask >> v & 1
                or v == i
                or (i < n - 1 and v == i + 1)
                or (i == n - 1 and first >= v)
            ):
                continue
            flip = sum(bool(mask >> w & 1) for w in range(v + 1, n)) % 2
            result = dp(n, mask | (1 << v), v if i == 0 else first, parity ^ flip)
            for k in range(2):
                counts[k] += result[k]
        return tuple(counts)

    all_counts = {}
    for n in (4, 5, 7):
        all_counts[n] = enumerate_n(n)
        assert all_counts[n] == dp(n, 0, -1, 0)
    even, odd = all_counts[7]
    return {
        "count4": sum(all_counts[4]),
        "count5": sum(all_counts[5]),
        "parity7": [even, odd],
        "count7": even + odd,
    }


ITEMS = [(4, 8), (5, 11), (6, 13), (3, 7), (2, 4), (4, 9), (5, 12), (1, 2)]


def selection():
    def feasible(ix, changed):
        s = set(ix)
        return (
            sum(ITEMS[i][0] for i in s) <= 15
            and not (2 in s and 4 not in s)
            and not (6 in s and 3 not in s)
            and not {0, 5} <= s
            and (changed or not {1, 6} <= s)
        )

    answers = []
    counts = []
    for changed in (False, True):
        options = [
            list(c)
            for r in range(9)
            for c in combinations(range(8), r)
            if feasible(c, changed)
        ]
        counts.append(len(options))
        ordered = sorted(
            options,
            key=lambda ix: (
                -sum(ITEMS[i][1] for i in ix),
                sum(ITEMS[i][0] for i in ix),
                ix,
            ),
        )
        ix = ordered[0]
        value = sum(ITEMS[i][1] for i in ix)
        answers.append(
            {
                "indices": ix,
                "value": value,
                "weight": sum(ITEMS[i][0] for i in ix),
                "value_ties": sum(
                    sum(ITEMS[i][1] for i in c) == value for c in options
                ),
            }
        )
        # 另一种位掩码枚举核对全部可行集合。
        masks = []
        for m in range(256):
            b = [(m >> i) & 1 for i in range(8)]
            if (
                sum(w * x for (w, _), x in zip(ITEMS, b)) > 15
                or b[2] > b[4]
                or b[6] > b[3]
                or b[0] + b[5] > 1
                or not changed
                and b[1] + b[6] > 1
            ):
                continue
            masks.append([i for i in range(8) if b[i]])
        assert sorted(masks) == sorted(options)
    return {
        "base": answers[0],
        "changed": answers[1],
        "feasible_counts": counts,
        "delta": answers[1]["value"] - answers[0]["value"],
    }


DURATIONS = [3, 2, 4, 3, 2, 2]
PREDECESSORS = [[], [], [0], [0], [1], [2, 3, 4]]


def schedules():
    def enumerate_starts(horizon, lock):
        result, starts, load = [], [0] * 6, [0] * horizon

        def visit(i):
            if i == 6:
                result.append(starts[:])
                return
            lower = max((starts[p] + DURATIONS[p] for p in PREDECESSORS[i]), default=0)
            for t in range(lower, horizon - DURATIONS[i] + 1):
                if any(load[j] >= 2 for j in range(t, t + DURATIONS[i])):
                    continue
                if (
                    lock
                    and i == 4
                    and max(t, starts[2])
                    < min(t + DURATIONS[i], starts[2] + DURATIONS[2])
                ):
                    continue
                starts[i] = t
                for j in range(t, t + DURATIONS[i]):
                    load[j] += 1
                visit(i + 1)
                for j in range(t, t + DURATIONS[i]):
                    load[j] -= 1

        visit(0)
        return result

    # 独立的时间展开搜索：状态是已完成集合和正在执行任务的剩余时间。
    def bfs(lock):
        states = {(0, ())}
        for time in range(30):
            next_states = set()
            for done, running in states:
                if done == 63:
                    return time
                occupied = {i for i, _ in running}
                ready = [
                    i
                    for i in range(6)
                    if not done >> i & 1
                    and i not in occupied
                    and all(done >> p & 1 for p in PREDECESSORS[i])
                ]
                for size in range(min(len(ready), 2 - len(running)) + 1):
                    for batch in combinations(ready, size):
                        if lock and {2, 4} <= occupied | set(batch):
                            continue
                        current = list(running) + [(i, DURATIONS[i]) for i in batch]
                        if not current:
                            continue
                        new_done = done
                        remaining = []
                        for i, ticks in current:
                            if ticks == 1:
                                new_done |= 1 << i
                            else:
                                remaining.append((i, ticks - 1))
                        next_states.add((new_done, tuple(sorted(remaining))))
            states = next_states
        raise AssertionError("schedule not found")

    base = enumerate_starts(10, True)
    changed = enumerate_starts(9, False)
    assert (
        base and not enumerate_starts(9, True) and bfs(True) == 10 and bfs(False) == 9
    )
    return {
        "lower_bounds": [9, 8],
        "base": {"makespan": 10, "starts": min(base)},
        "optimal_count": len(base),
        "changed": {"makespan": 9, "starts": min(changed)},
    }


def adaptive_gloves():
    left, right = (2, 3, 4), (3, 2, 4)

    @lru_cache(None)
    def value(a, b):
        if any(x and y for x, y in zip(a, b)):
            return 0
        choices = []
        for side, cap, d in [(0, left, a), (1, right, b)]:
            outcomes = []
            for i in range(3):
                if d[i] < cap[i]:
                    c = list(d)
                    c[i] += 1
                    outcomes.append(
                        value(tuple(c), b) if side == 0 else value(a, tuple(c))
                    )
            if outcomes:
                choices.append(1 + max(outcomes))
        return min(choices) if choices else 99

    zero = (0, 0, 0)
    branches = [value(tuple(int(j == i) for j in range(3)), zero) for i in range(3)]
    states = [
        (a, b)
        for a in product(*(range(x + 1) for x in left))
        for b in product(*(range(x + 1) for x in right))
    ]
    table = {}
    for a, b in sorted(states, key=lambda s: -sum(s[0]) - sum(s[1])):
        if any(x and y for x, y in zip(a, b)):
            table[a, b] = 0
            continue
        choices = []
        for side, cap, d in [(0, left, a), (1, right, b)]:
            outcomes = []
            for i in range(3):
                if d[i] < cap[i]:
                    c = list(d)
                    c[i] += 1
                    outcomes.append(
                        table[tuple(c), b] if side == 0 else table[a, tuple(c)]
                    )
            if outcomes:
                choices.append(1 + max(outcomes))
        table[a, b] = min(choices) if choices else 99
    assert all(value(a, b) == table[a, b] for a, b in states)
    bad = {
        (sum(a), sum(b)) for a, b in states if not any(x and y for x, y in zip(a, b))
    }
    fixed = min(l + r for l in range(10) for r in range(10) if (l, r) not in bad)
    first = [
        1 + max(branches),
        1 + max(value(zero, tuple(int(j == i) for j in range(3))) for i in range(3)),
    ]
    return {
        "fixed": fixed,
        "after_first_left": branches,
        "first_action_costs": first,
        "adaptive": value(zero, zero),
    }


def dominoes():
    rows, cols = 4, 7
    cells = {(r, c) for r in range(rows) for c in range(cols)} - {(0, 0), (3, 6)}
    tilings = []

    def visit(left, pairs):
        if not left:
            tilings.append(tuple(sorted(pairs)))
            return
        a = min(left)
        for b in ((a[0] + 1, a[1]), (a[0], a[1] + 1)):
            if b in left:
                visit(left - {a, b}, pairs + [(a, b)])

    visit(cells, [])
    histogram = Counter(sum(a[0] == b[0] for a, b in t) for t in tilings)
    selected = [t for t in tilings if sum(a[0] == b[0] for a, b in t) == 10]
    rotate = lambda t: tuple(
        sorted(
            tuple(
                sorted(
                    (
                        (rows - 1 - a[0], cols - 1 - a[1]),
                        (rows - 1 - b[0], cols - 1 - b[1]),
                    )
                )
            )
            for a, b in t
        )
    )
    fixed = sum(rotate(t) == t for t in selected)
    orbits = len({min(t, rotate(t)) for t in selected})
    assert 2 * orbits == len(selected) + fixed
    # 独立按列轮廓递推，记录水平骨牌数的多项式。
    blocked = {0: 1, 6: 8}
    dp = {(0, 0): 1}
    for col in range(cols):
        next_dp = Counter()
        for (incoming, h), count in dp.items():
            holes = blocked.get(col, 0)
            if incoming & holes:
                continue

            def fill(mask, out, added):
                if mask == 15:
                    next_dp[out, h + added] += count
                    return
                row = next(r for r in range(rows) if not mask >> r & 1)
                if row + 1 < rows and not mask >> (row + 1) & 1:
                    fill(mask | 1 << row | 1 << (row + 1), out, added)
                if col + 1 < cols and not blocked.get(col + 1, 0) >> row & 1:
                    fill(mask | 1 << row, out | 1 << row, added + 1)

            fill(incoming | holes, 0, 0)
        dp = next_dp
    assert dict(histogram) == {h: count for (mask, h), count in dp.items() if mask == 0}
    return {
        "horizontal_histogram": [[h, histogram[h]] for h in sorted(histogram)],
        "selected": len(selected),
        "rotation_fixed": fixed,
        "orbits": orbits,
    }


REASONING_ORACLES = {
    "R-E-01": coins,
    "R-E-02": urn,
    "R-N-01": glove_fixed,
    "R-N-02": restricted_permutations,
    "R-H-01": schedules,
    "R-H-02": selection,
    "R-X-01": adaptive_gloves,
    "R-X-02": dominoes,
}


def brute_weighted_schedule(data):
    jobs = data["jobs"]
    candidates = []
    for mask in range(1 << len(jobs)):
        chosen = sorted(
            (j for i, j in enumerate(jobs) if mask >> i & 1),
            key=lambda j: (j["start"], j["end"], j["id"]),
        )
        if any(a["end"] > b["start"] for a, b in zip(chosen, chosen[1:])):
            continue
        candidates.append((sum(j["value"] for j in chosen), [j["id"] for j in chosen]))
    value, ids = min(candidates, key=lambda x: (-x[0], len(x[1]), x[1]))
    return {"value": value, "ids": ids}


def bfs_connectivity(data):
    counts = Counter()
    answers = []
    for op, u, v in data["events"]:
        edge = tuple(sorted((u, v)))
        if op == "ADD":
            counts[edge] += 1
        elif op == "REMOVE":
            counts[edge] = max(0, counts[edge] - 1)
        else:
            graph = [[] for _ in range(data["n"])]
            for (a, b), n in counts.items():
                if n:
                    graph[a].append(b)
                    graph[b].append(a)
            seen = {u}
            queue = deque([u])
            while queue:
                a = queue.popleft()
                for b in graph[a]:
                    if b not in seen:
                        seen.add(b)
                        queue.append(b)
            answers.append(v in seen)
    return answers
