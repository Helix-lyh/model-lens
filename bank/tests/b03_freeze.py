from solution import FreezeBag

n = 0
try:
    bag = FreezeBag(2)
    bag.put("a", 1)
    bag.put("b", 2)
    n += int(bag.get("a") == 1)
    bag.freeze("a")
    bag.put("c", 3)
    n += int(bag.get("a") == 1)
    n += int(bag.get("b") is None)
    n += int(bag.get("c") == 3)
except Exception as exc:
    print("MISS", type(exc).__name__)
print(f"POINTS {n}/4")
