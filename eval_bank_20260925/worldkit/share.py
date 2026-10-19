"""两台同时工作时按分钟各走半格。充电、后厨并灶、床位护理共用。"""
from __future__ import annotations


def dual_progress(
    starts: list[int],
    sides: list[int],
    needs: list[int],
    share: bool,
    block: tuple[int, int] | None = None,
) -> list[int]:
    """sides[i] 为 0/1。block 只让 side 0 在 [lo, hi) 停。返回各任务完成时刻。"""
    n = len(starts)
    got = [0] * n
    half = [0] * n
    done = [-1] * n
    left = n
    t = 0
    lo, hi = block if block else (1, 0)
    while left:
        busy0 = busy1 = False
        for i in range(n):
            if done[i] >= 0 or starts[i] > t:
                continue
            if sides[i] == 0 and lo <= t < hi:
                continue
            if sides[i] == 0:
                busy0 = True
            else:
                busy1 = True
        if not busy0 and not busy1:
            nxt = None
            for i in range(n):
                if done[i] < 0 and (nxt is None or starts[i] < nxt):
                    nxt = starts[i]
            if nxt is None or nxt <= t:
                nxt = t + 1
            if lo <= t < hi and nxt > hi:
                t = hi
            else:
                t = nxt
            continue
        for i in range(n):
            if done[i] >= 0 or starts[i] > t:
                continue
            if sides[i] == 0 and lo <= t < hi:
                continue
            other = busy1 if sides[i] == 0 else busy0
            if share and other:
                half[i] += 1
                if half[i] == 2:
                    got[i] += 1
                    half[i] = 0
            else:
                half[i] = 0
                got[i] += 1
            if got[i] >= needs[i]:
                done[i] = t + 1
                left -= 1
        t += 1
        if t > 20000:
            raise RuntimeError("dual_progress did not finish")
    return done


def stabilize(
    starts: list[int],
    sides: list[int],
    needs: list[int],
    share: bool,
    gaps: list[int],
    ready: list[int] | None = None,
    block: tuple[int, int] | None = None,
) -> list[int]:
    """半格拉长前一单后，后一单开工不得早于同侧完成加空等。starts 就地抬高。"""
    ready = ready or [0] * len(starts)
    for _ in range(64):
        done = dual_progress(starts, sides, needs, share, block) if share else [
            s + n for s, n in zip(starts, needs)
        ]
        last = {}
        bumped = False
        for i in range(len(starts)):
            s = sides[i]
            floor = max(ready[i], last.get(s, 0) + gaps[i])
            if starts[i] < floor:
                starts[i] = floor
                bumped = True
            last[s] = done[i]
        if not bumped:
            return done
    raise RuntimeError("stabilize did not settle")
