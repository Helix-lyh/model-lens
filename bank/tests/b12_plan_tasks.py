from solution import plan_tasks


def _hit(tasks, deps, expect, name) -> int:
    try:
        got = plan_tasks(tasks, deps)
        if got is not None:
            got = list(got)
        ok = got == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit(["c", "a", "b"], [], ["a", "b", "c"], "no-deps")
n += _hit(["a", "b", "c"], [("a", "b"), ("b", "c")], ["c", "b", "a"], "chain")
n += _hit(["d", "b", "c", "a"], [("b", "a"), ("c", "a"), ("d", "b"), ("d", "c")], ["a", "b", "c", "d"], "diamond")
n += _hit(["a", "b"], [("a", "b"), ("b", "a")], None, "cycle")
n += _hit(["a", "b"], [("b", "a"), ("b", "a")], ["a", "b"], "dup-deps")
n += _hit(["t3", "t1", "x", "t2"], [("t2", "t1"), ("t3", "t2"), ("x", "t1")], ["t1", "t2", "t3", "x"], "mixed")
print(f"POINTS {n}/6")
