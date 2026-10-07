from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from eval_bank_20260925 import runtime_profiles
from eval_bank_20260925 import bank_manifest
from src.grade import run_go_sandbox, run_python_sandbox, run_ts_sandbox


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_profile_registry_requires_language_lockfiles_and_hashes() -> None:
    registry = runtime_profiles.RuntimeProfileRegistry()
    with pytest.raises(ValueError, match="requires lockfiles"):
        registry.register(runtime_profiles.RuntimeProfile("bad", "go", (("go.mod", "0" * 64),)))
    with pytest.raises(ValueError, match="SHA-256"):
        registry.register(runtime_profiles.RuntimeProfile(
            "bad", "python", (("requirements.lock", "not-a-hash"),)))


def test_manifest_profile_specs_install_through_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bank_manifest, "RUNTIME_PROFILE_SPECS", ({
        "id": "manifest-test-profile", "language": "go",
        "lockfiles": (("go.mod", "a" * 64), ("go.sum", "b" * 64)),
    },))
    runtime_profiles.install_manifest_profiles()
    assert runtime_profiles.RUNTIME_PROFILES.resolve("manifest-test-profile").language == "go"


def test_profile_lockfile_hash_is_verified_before_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("sample==1.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    profile = runtime_profiles.RuntimeProfile("hash-check", "python",
                                               (("requirements.lock", "0" * 64),))
    runtime_profiles.RUNTIME_PROFILES.register(profile, replace=True)
    monkeypatch.setattr(runtime_profiles, "repo_root", lambda: tmp_path)
    with pytest.raises(runtime_profiles.RuntimeProfileError, match="hash mismatch"):
        runtime_profiles.prepare_profile(profile.id)


def test_profile_preparation_is_content_addressed_and_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("sample==1.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    profile = runtime_profiles.RuntimeProfile("cache-check", "python",
                                               (("requirements.lock", _sha(lock)),))
    runtime_profiles.RUNTIME_PROFILES.register(profile, replace=True)
    monkeypatch.setattr(runtime_profiles, "repo_root", lambda: tmp_path)
    calls = []

    def install(_profile, _locks, dest):
        calls.append(dest)
        package_dir = dest / "site-packages"
        package_dir.mkdir()
        (package_dir / "locked_dep.py").write_text("VALUE = 7\n", encoding="utf-8")

    monkeypatch.setattr(runtime_profiles, "_install", install)
    first = runtime_profiles.prepare_profile(profile.id)
    second = runtime_profiles.prepare_profile(profile.id)
    assert first.profile_sha256 == second.profile_sha256
    assert first.root == second.root
    assert len(calls) == 1


def test_profile_cache_identity_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("sample==1.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    profile = runtime_profiles.RuntimeProfile("cache-mismatch", "python",
                                               (("requirements.lock", _sha(lock)),))
    runtime_profiles.RUNTIME_PROFILES.register(profile, replace=True)
    monkeypatch.setattr(runtime_profiles, "repo_root", lambda: tmp_path)
    cache = tmp_path / ".cache" / "runtime-profiles" / profile.id / runtime_profiles._profile_hash(profile)
    cache.mkdir(parents=True)
    (cache / "READY.json").write_text('{"profile_id":"other"}', encoding="utf-8")
    with pytest.raises(runtime_profiles.RuntimeProfileError, match="identity mismatch"):
        runtime_profiles.prepare_profile(profile.id)


def test_python_sandbox_can_import_profile_package(tmp_path: Path) -> None:
    deps = tmp_path / "site-packages"
    deps.mkdir()
    (deps / "locked_dep.py").write_text("VALUE = 7\n", encoding="utf-8")
    test_file = tmp_path / "test.py"
    test_file.write_text(
        "from locked_dep import VALUE\n"
        "from solution import solve\n"
        "assert solve() == VALUE\n"
        "print('__PROFILE__ POINTS 1/1')\n",
        encoding="utf-8",
    )
    status, detail = run_python_sandbox(
        "def solve(): return 7", test_file, result_marker="__PROFILE__",
        runtime={"python_path": str(deps)},
    )
    assert (status, "POINTS 1/1" in detail) == ("pass", True)


def test_go_sandbox_uses_profile_locked_module_files(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module solution\n\ngo 1.20\n", encoding="utf-8")
    (tmp_path / "go.sum").write_text("", encoding="utf-8")
    module_cache = tmp_path / "gomodcache"
    module_cache.mkdir()
    test_file = tmp_path / "solution_test.go"
    test_file.write_text(
        'package solution\nimport ("fmt"; "testing")\n'
        'func TestProfile(t *testing.T) { if Solve()!=7 { t.Fatal("bad") }; fmt.Println("__PROFILE__ POINTS 1/1") }\n',
        encoding="utf-8",
    )
    status, detail = run_go_sandbox(
        "package solution\nfunc Solve() int { return 7 }", test_file,
        result_marker="__PROFILE__",
        runtime={"go_modfile": str(tmp_path / "go.mod"), "go_sumfile": str(tmp_path / "go.sum"),
                 "go_modcache": str(module_cache)},
    )
    assert (status, "POINTS 1/1" in detail) == ("pass", True)


def test_typescript_sandbox_resolves_profile_node_modules(tmp_path: Path) -> None:
    modules = tmp_path / "node_modules" / "locked-dep"
    modules.mkdir(parents=True)
    (modules / "index.js").write_text("exports.value = 7;\n", encoding="utf-8")
    (modules / "index.d.ts").write_text("export const value: number;\n", encoding="utf-8")
    test_file = tmp_path / "test.ts"
    test_file.write_text(
        'declare const require: any;\n'
        'const {solve} = require("./solution");\n'
        'const {value} = require("locked-dep");\n'
        'if (solve() !== value) throw new Error("bad");\n'
        'console.log("__PROFILE__ POINTS 1/1");\n',
        encoding="utf-8",
    )
    status, detail = run_ts_sandbox(
        'export function solve(): number { return 7; }', test_file,
        result_marker="__PROFILE__", runtime={"node_modules": str(tmp_path / "node_modules")},
    )
    assert (status, "POINTS 1/1" in detail) == ("pass", True)
