"""定位编码沙箱工具链。缺工具记 missing，不记模型 0 分。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CODE_LANGS = ("python", "go", "typescript")
TSC_VERSION = "5.8.2"
PY_MIN = (3, 11)
GO_MIN = (1, 20)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cache_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / ".cache"


def _extra_bins() -> list[Path]:
    home = Path.home()
    extras = [
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/local/go/bin"),
        home / "go" / "bin",
    ]
    nvm = home / ".nvm" / "versions" / "node"
    if nvm.is_dir():
        extras.extend(sorted((p / "bin" for p in nvm.iterdir() if p.is_dir()), reverse=True))
    return extras


def search_path() -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for raw in os.environ.get("PATH", "").split(os.pathsep):
        if raw and raw not in seen:
            seen.add(raw)
            parts.append(raw)
    for extra in _extra_bins():
        key = str(extra)
        if extra.is_dir() and key not in seen:
            seen.add(key)
            parts.append(key)
    return os.pathsep.join(parts)


def which(name: str) -> str | None:
    return shutil.which(name, path=search_path())


def _run_version(argv: list[str]) -> str | None:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return None
    blob = f"{proc.stdout or ''}{proc.stderr or ''}".strip()
    return blob.splitlines()[0] if blob else None


@dataclass(frozen=True)
class Tool:
    name: str
    path: str | None
    argv: tuple[str, ...] = ()
    version: str | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        if not (self.argv or self.path):
            return False
        if self.name == "python":
            return _meets_min(self.version, PY_MIN)
        if self.name == "go":
            return _meets_min(self.version, GO_MIN)
        return True


@dataclass(frozen=True)
class Toolchain:
    python: Tool
    go: Tool
    node: Tool
    tsc: Tool

    def missing_for(self, lang: str) -> list[str]:
        needed: list[Tool]
        if lang == "python":
            needed = [self.python]
        elif lang == "go":
            needed = [self.go]
        elif lang == "typescript":
            needed = [self.node, self.tsc]
        else:
            return [lang]
        return [tool.name for tool in needed if not tool.ok]


def _parse_major_minor(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    match = re.search(r"(\d+)\.(\d+)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _meets_min(version: str | None, floor: tuple[int, int]) -> bool:
    parsed = _parse_major_minor(version)
    return parsed is not None and parsed >= floor


def _python_tool() -> Tool:
    venv = repo_root() / ".venv" / "bin" / "python"
    path = str(venv) if venv.is_file() else (which("python3") or which("python"))
    version = _run_version([path, "--version"]) if path else None
    return Tool(
        name="python",
        path=path,
        argv=(path,) if path else (),
        version=version,
        detail="" if _meets_min(version, PY_MIN) or not path else f"需要 Python {PY_MIN[0]}.{PY_MIN[1]}+",
    )


def _go_tool() -> Tool:
    path = which("go")
    version = _run_version([path, "version"]) if path else None
    return Tool(
        name="go",
        path=path,
        argv=(path,) if path else (),
        version=version,
        detail="" if _meets_min(version, GO_MIN) or not path else f"需要 go >={GO_MIN[0]}.{GO_MIN[1]}",
    )


def _node_tool() -> Tool:
    path = which("node")
    version = _run_version([path, "--version"]) if path else None
    return Tool(name="node", path=path, argv=(path,) if path else (), version=version)


def tsc_bin(root: Path | None = None) -> Path:
    return cache_dir(root) / "tsc" / "node_modules" / ".bin" / "tsc"


def _tsc_tool() -> Tool:
    cached = tsc_bin()
    if cached.is_file():
        path = str(cached)
        return Tool(
            name="tsc",
            path=path,
            argv=(path,),
            version=_run_version([path, "--version"]),
            detail=f"cache typescript@{TSC_VERSION}",
        )
    path = which("tsc")
    if path:
        return Tool(name="tsc", path=path, argv=(path,), version=_run_version([path, "--version"]))
    node = which("node")
    if node:
        sibling = Path(node).parent / "tsc"
        if sibling.is_file():
            return Tool(
                name="tsc",
                path=str(sibling),
                argv=(str(sibling),),
                version=_run_version([str(sibling), "--version"]),
            )
    npx = which("npx")
    if npx:
        argv = (npx, "--yes", "-p", f"typescript@{TSC_VERSION}", "tsc")
        return Tool(name="tsc", path=npx, argv=argv, detail=f"npx typescript@{TSC_VERSION}")
    return Tool(name="tsc", path=None, detail="需要 tsc 或 npx")


def discover() -> Toolchain:
    return Toolchain(python=_python_tool(), go=_go_tool(), node=_node_tool(), tsc=_tsc_tool())


def ensure_tsc(root: Path | None = None) -> Tool:
    root = root or repo_root()
    dest = cache_dir(root) / "tsc"
    dest.mkdir(parents=True, exist_ok=True)
    npm = which("npm")
    if not npm:
        return Tool(name="tsc", path=None, detail="需要 npm 才能安装 typescript")
    proc = subprocess.run(
        [npm, "install", f"typescript@{TSC_VERSION}", "--prefix", str(dest), "--no-fund", "--no-audit"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        blob = f"{proc.stdout or ''}{proc.stderr or ''}".strip()
        return Tool(name="tsc", path=None, detail=blob[-300:] or "npm install typescript 失败")
    return _tsc_tool()


def ensure_cache_dirs(root: Path | None = None) -> Path:
    root = cache_dir(root)
    (root / "gocache").mkdir(parents=True, exist_ok=True)
    (root / "tsc").mkdir(parents=True, exist_ok=True)
    return root
