"""Verify Python bank tests and structure tests against known-good answers."""

from __future__ import annotations

from src.bank import repo_root
from src.grade import run_sandbox

ROOT = repo_root()

PY = {
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
}

STRUCTURE = {
    "bank/tests/c09_lines6.py": "[[v2]]\nsgnl\nsgnl-sgnl\n9\nlngs\n[[end]]",
    "bank/tests/c10_meta.py": '{"data": ["0", 0, false, null], "meta": {"v": 1e2, "k k": {}}}',
    "bank/tests/c11_logic_grid.py": (
        '{"A": {"floor": 2, "drink": "茶"}, "B": {"floor": 3, "drink": "咖啡"},'
        ' "C": {"floor": 1, "drink": "可乐"}}'
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
