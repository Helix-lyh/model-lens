#!/usr/bin/env python3
"""环境初始化：.venv + go/node 检查 + 钉死 typescript 5.8.2。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _venv_python() -> Path:
    return ROOT / ".venv" / "bin" / "python"


def _ensure_venv() -> Path:
    py = _venv_python()
    if py.is_file():
        return py
    candidates = ["python3.11", "python3.12", "python3"]
    exe = next((c for c in candidates if _ok_python(c)), None)
    if not exe:
        raise SystemExit("需要 Python 3.11+ 才能建立 .venv")
    subprocess.run([exe, "-m", "venv", str(ROOT / ".venv")], check=True)
    return py


def _ok_python(cmd: str) -> bool:
    from shutil import which

    path = which(cmd)
    if not path:
        return False
    proc = subprocess.run(
        [path, "-c", "import sys; sys.exit(sys.version_info < (3, 11))"],
        capture_output=True, text=True,
    )
    return proc.returncode == 0


def _install_dev(py: Path) -> None:
    uv = ROOT / ".venv" / "bin" / "uv"
    from shutil import which

    uv_bin = str(uv) if uv.is_file() else which("uv")
    if uv_bin:
        subprocess.run([uv_bin, "pip", "install", "-p", str(py), "-e", f"{ROOT}[dev]"], check=True)
        return
    subprocess.run([str(py), "-m", "pip", "install", "-e", f"{ROOT}[dev]"], check=True)


def _print_report(tools, *, header: str) -> int:
    print(header)
    rows = [tools.python, tools.go, tools.node, tools.tsc]
    failed = 0
    for tool in rows:
        mark = "ok" if tool.ok else "MISSING"
        if mark != "ok":
            failed += 1
        loc = tool.path or "-"
        extra = f"  {tool.detail}" if tool.detail else ""
        print(f"  {mark:7} {tool.name:8} {tool.version or '-':20} {loc}{extra}")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="model-lens 环境初始化")
    parser.add_argument("--check", action="store_true", help="只检查，不建 venv / 不装 tsc")
    args = parser.parse_args()

    if not args.check:
        py = _ensure_venv()
        _install_dev(py)
        from src.toolchain import ensure_cache_dirs, ensure_tsc

        ensure_cache_dirs(ROOT)
        tsc = ensure_tsc(ROOT)
        if not tsc.ok:
            print(f"tsc 安装失败：{tsc.detail}", file=sys.stderr)

    from src.toolchain import discover

    tools = discover()
    failed = _print_report(tools, header="工具链：" if args.check else "初始化后：")
    if failed:
        print("缺工具时：对应语言编码题记 missing，不记模型 0 分。先装 go / node，再重新跑本脚本。")
        return 1
    print("环境可用。跑测请用 .venv/bin/pytest 或 .venv/bin/python -m src.cli …")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
