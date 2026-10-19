"""把门禁交给常驻的 Go 进程。变体之间并行，引擎和复核器仍是两份实现。"""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = Path(__file__).resolve().parent / "gosolve"
_BIN = _ROOT / ".cache" / "worldkit-solve"
_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_seq = 0


def _fresh() -> bool:
    if not _BIN.exists():
        return False
    built = _BIN.stat().st_mtime
    return all(p.stat().st_mtime <= built for p in _SRC.rglob("*.go"))


def _ensure() -> None:
    if _fresh():
        return
    _BIN.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["go", "build", "-o", str(_BIN), "."], cwd=_SRC, check=True)


def _client() -> subprocess.Popen:
    global _proc
    if _proc is not None and _proc.poll() is None and _fresh():
        return _proc
    if _proc is not None and _proc.poll() is None:
        _proc.kill()
        _proc.wait(timeout=5)
    _proc = None
    _ensure()
    _proc = subprocess.Popen(
        [str(_BIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    return _proc


def _call(payload: dict) -> dict:
    global _proc, _seq
    with _lock:
        _seq += 1
        payload = dict(payload, id=_seq)
        proc = _client()
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            _proc = None
            raise RuntimeError("worldkit Go 求解进程退出")
        msg = json.loads(line)
    if msg.get("error"):
        raise RuntimeError(msg["error"])
    return msg["report"]


def status(world: dict, *, max_plans: int, seconds: float) -> dict:
    return _call({"op": "status", "world": world, "max_plans": max_plans, "seconds": seconds})


def trajectory(world: dict, *, max_plans: int, seconds: float) -> dict:
    return _call({"op": "trajectory", "world": world, "max_plans": max_plans, "seconds": seconds})


def run_gates(world: dict, *, fail_fast: bool, max_plans: int, seconds: float) -> dict:
    return _call({"op": "gates", "world": world, "fail_fast": fail_fast,
                  "max_plans": max_plans, "seconds": seconds})
