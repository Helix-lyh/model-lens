from solution import render


def _hit(template, vars, expect, name) -> int:
    try:
        ok = render(template, vars) == expect
    except Exception:
        ok = False
    print("HIT" if ok else "MISS", name)
    return int(ok)


n = 0
n += _hit("hello", {}, "hello", "plain")
n += _hit("hi {name}!", {"name": "Tom"}, "hi Tom!", "replace")
n += _hit("{a}+{b}", {"a": "1"}, "1+{b}", "missing-kept")
n += _hit("{{name}}", {"name": "X"}, "{name}", "escape")
n += _hit("{a b} { {}", {}, "{a b} { {}", "invalid-kept")
n += _hit("{x}{{y}}{z}", {"x": "1", "z": "2"}, "1{y}2", "mixed")
n += _hit("{{{name}}}", {"name": "Tom"}, "{Tom}", "triple")
n += _hit("{{y}}", {"y": "Y"}, "{y}", "escape-over-var")
print(f"POINTS {n}/8")
