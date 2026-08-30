from __future__ import annotations

from src.toolchain import CODE_LANGS, Tool, Toolchain, _parse_major_minor, discover


def test_discover_python_and_lang_names() -> None:
    tools = discover()
    assert CODE_LANGS == ("python", "go", "typescript")
    assert tools.python.ok
    assert tools.missing_for("python") == []


def test_parse_major_minor_python_and_go() -> None:
    assert _parse_major_minor("Python 3.10.14") == (3, 10)
    assert _parse_major_minor("Python 3.11.0") == (3, 11)
    assert _parse_major_minor("go version go1.19.13 linux/amd64") == (1, 19)
    assert _parse_major_minor("go version go1.20.0 linux/amd64") == (1, 20)
    assert _parse_major_minor(None) is None
    assert _parse_major_minor("") is None
    assert _parse_major_minor("no-dots") is None


def test_tool_ok_requires_version_floor() -> None:
    old_py = Tool("python", "/usr/bin/python3", argv=("/usr/bin/python3",), version="Python 3.10.14")
    new_py = Tool("python", "/usr/bin/python3", argv=("/usr/bin/python3",), version="Python 3.11.0")
    old_go = Tool("go", "/usr/bin/go", argv=("/usr/bin/go",), version="go version go1.19.13 linux/amd64")
    new_go = Tool("go", "/usr/bin/go", argv=("/usr/bin/go",), version="go version go1.20.0 linux/amd64")
    assert old_py.ok is False
    assert new_py.ok is True
    assert old_go.ok is False
    assert new_go.ok is True
    assert Tool("go", None).ok is False
    stale = Toolchain(python=old_py, go=old_go, node=Tool("node", None), tsc=Tool("tsc", None))
    assert stale.missing_for("python") == ["python"]
    assert stale.missing_for("go") == ["go"]


def test_init_env_check_exits_clean() -> None:
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    script = root / "cursor_workspace" / "build_scripts" / "init_env.py"
    proc = subprocess.run([str(root / ".venv" / "bin" / "python"), str(script), "--check"], capture_output=True, text=True)
    assert "python" in proc.stdout
    assert proc.returncode in {0, 1}
