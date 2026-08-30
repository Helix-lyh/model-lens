import threading

from solution import SafeCounter

n = 0
try:
    c = SafeCounter()
    threads = [threading.Thread(target=lambda: [c.increment() for _ in range(200)]) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    n += int(c.value() == 1600)
except Exception as exc:
    print("MISS", type(exc).__name__)
print(f"POINTS {n}/1")
