"""被测代码读不到宿主密钥与家目录。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.grade as grade

PROBE = '''
import json, os
def probe(secret_path):
    try:
        leaked = open(secret_path).read()
    except OSError:
        leaked = None
    return {"home": os.environ.get("HOME"), "key": os.environ.get("BOOSTER_API_KEY"),
            "leaked": leaked, "grok": os.path.exists(os.path.expanduser("~/.grok/auth.json"))}
'''


def _run(tmp_path: Path, secret: Path) -> dict:
    tests = tmp_path / "tests" / "t.py"
    tests.parent.mkdir()
    tests.write_text(
        "import json\nfrom solution import probe\n"
        f"print('MARK CASE 0 ' + json.dumps(probe({str(secret)!r})))\n",
        encoding="utf-8",
    )
    status, detail = grade.run_python_sandbox(PROBE, tests, result_marker="MARK")
    line = next(x for x in detail.splitlines() if x.startswith("CASE 0 "))
    return json.loads(line[len("CASE 0 "):])


def test_python_sandbox_hides_env_keys_and_uses_temp_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BOOSTER_API_KEY", "sk-test-not-real")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET", encoding="utf-8")
    seen = _run(tmp_path, secret)
    assert seen["key"] is None
    assert seen["home"] and seen["home"] != str(Path.home())
    assert seen["grok"] is False
    if grade.bwrap_usable():
        assert seen["leaked"] is None


def test_env_only_fallback_still_uses_temp_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MODEL_LENS_SANDBOX", "env")
    monkeypatch.setenv("BOOSTER_API_KEY", "sk-test-not-real")
    seen = _run(tmp_path, tmp_path / "missing")
    assert seen["key"] is None
    assert seen["home"] != str(Path.home())


def test_isolate_hides_home_and_workspace(tmp_path: Path):
    if not grade.bwrap_usable():
        pytest.skip("bubblewrap 不可用")
    argv = grade.isolate(["/bin/true"], tmp_path)
    joined = " ".join(argv)
    for hidden in ("--tmpfs /home", "--tmpfs /workspace", "--tmpfs /tmp", "--unshare-net"):
        assert hidden in joined
