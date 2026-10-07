"""Per-item locked dependency environments, separate from bank scoring."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.toolchain import discover, repo_root, search_path, which


Language = Literal["python", "go", "typescript"]


@dataclass(frozen=True)
class RuntimeProfile:
    id: str
    language: Language
    lockfiles: tuple[tuple[str, str], ...]
    allow_source: bool = False


@dataclass(frozen=True)
class RuntimeEnvironment:
    profile_id: str
    profile_sha256: str
    language: Language
    root: Path
    python_path: Path | None = None
    go_modcache: Path | None = None
    go_modfile: Path | None = None
    go_sumfile: Path | None = None
    node_modules: Path | None = None


class RuntimeProfileError(RuntimeError):
    def __init__(self, reason: Literal["missing", "error"], message: str):
        super().__init__(message)
        self.reason = reason


class RuntimeProfileRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, RuntimeProfile] = {}

    def register(self, profile: RuntimeProfile, *, replace: bool = False) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", profile.id) or profile.language not in {"python", "go", "typescript"}:
            raise ValueError("runtime profile requires an id and supported language")
        if profile.id in self._profiles and not replace:
            raise ValueError(f"runtime profile already registered: {profile.id}")
        expected = {"python": {"requirements.lock"}, "go": {"go.mod", "go.sum"},
                    "typescript": {"package.json", "package-lock.json"}}[profile.language]
        names = {Path(path).name for path, _ in profile.lockfiles}
        if names != expected or len(profile.lockfiles) != len(expected):
            raise ValueError(f"{profile.language} profile requires lockfiles {sorted(expected)}")
        if any(not _is_sha256(digest) for _, digest in profile.lockfiles):
            raise ValueError("runtime profile lockfile hashes must be lowercase SHA-256")
        self._profiles[profile.id] = profile

    def resolve(self, profile_id: str) -> RuntimeProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise RuntimeProfileError("error", f"unknown runtime profile: {profile_id}") from exc

    def __contains__(self, profile_id: str) -> bool:
        return profile_id in self._profiles


RUNTIME_PROFILES = RuntimeProfileRegistry()


def validate_manifest_profiles() -> None:
    from .bank_manifest import BANKS_BY_ITEM, ITEM_RUNTIME_PROFILES

    for item_id, by_language in ITEM_RUNTIME_PROFILES.items():
        if item_id not in BANKS_BY_ITEM:
            raise ValueError(f"runtime profile binding references unknown item: {item_id}")
        for language, profile_id in by_language.items():
            profile = RUNTIME_PROFILES.resolve(profile_id)
            if profile.language != language:
                raise ValueError(
                    f"runtime profile {profile_id!r} for {item_id}/{language} "
                    f"uses language {profile.language!r}"
                )


def install_manifest_profiles() -> None:
    from .bank_manifest import RUNTIME_PROFILE_SPECS

    for spec in RUNTIME_PROFILE_SPECS:
        RUNTIME_PROFILES.register(RuntimeProfile(
            id=str(spec["id"]),
            language=spec["language"],  # type: ignore[arg-type]
            lockfiles=tuple((str(path), str(digest)) for path, digest in spec["lockfiles"]),
            allow_source=bool(spec.get("allow_source", False)),
        ))


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def profile_for_item(item_id: str, language: str | None) -> str | None:
    """Resolve the optional manifest binding without coupling scorers to installs."""
    if language is None:
        return None
    from .bank_manifest import ITEM_RUNTIME_PROFILES

    return ITEM_RUNTIME_PROFILES.get(item_id, {}).get(language)


def profile_provenance(item_id: str, language: str | None) -> dict[str, str | None]:
    profile_id = profile_for_item(item_id, language)
    if profile_id is None:
        return {"runtime_profile_id": None, "runtime_profile_sha256": None}
    profile = RUNTIME_PROFILES.resolve(profile_id)
    digest = _profile_hash(profile)
    return {"runtime_profile_id": profile_id, "runtime_profile_sha256": digest}


def prepare_profile(profile_id: str, *, root: Path | None = None) -> RuntimeEnvironment:
    repo = root or repo_root()
    profile = RUNTIME_PROFILES.resolve(profile_id)
    lock_paths: dict[str, Path] = {}
    for relative, expected in profile.lockfiles:
        path = (repo / relative).resolve()
        if not path.is_relative_to(repo.resolve()) or not path.is_file():
            raise RuntimeProfileError("error", f"runtime lockfile missing or outside repository: {relative}")
        actual = _file_hash(path)
        if actual != expected:
            raise RuntimeProfileError("error", f"runtime lockfile hash mismatch: {relative}")
        lock_paths[path.name] = path
    _validate_lock_contents(profile, lock_paths)

    digest = _profile_hash(profile)
    cache = repo / ".cache" / "runtime-profiles" / profile.id / digest
    ready = cache / "READY.json"
    if cache.exists() and not ready.is_file():
        raise RuntimeProfileError("error", f"runtime cache has no identity marker: {cache}")
    if ready.is_file():
        try:
            record = json.loads(ready.read_text(encoding="utf-8"))
            if record == {"profile_id": profile.id, "profile_sha256": digest}:
                return _environment(profile, digest, cache)
            raise RuntimeProfileError("error", f"runtime cache identity mismatch: {cache}")
        except RuntimeProfileError:
            raise
        except (OSError, ValueError):
            pass

    cache.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".prepare-", dir=cache.parent))
    try:
        _install(profile, lock_paths, staging)
        (staging / "READY.json").write_text(
            json.dumps({"profile_id": profile.id, "profile_sha256": digest}, sort_keys=True),
            encoding="utf-8",
        )
        try:
            staging.rename(cache)
        except FileExistsError:
            try:
                record = json.loads(ready.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise
            if record != {"profile_id": profile.id, "profile_sha256": digest}:
                raise RuntimeProfileError("error", f"runtime cache identity mismatch: {cache}")
        return _environment(profile, digest, cache)
    except RuntimeProfileError:
        raise
    except Exception as exc:
        raise RuntimeProfileError("error", f"dependency preparation failed: {exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def environment_for_item(item_id: str, language: str | None) -> tuple[str | None, dict[str, str] | None]:
    profile_id = profile_for_item(item_id, language)
    if profile_id is None:
        return None, None
    env = prepare_profile(profile_id)
    values = {
        "python_path": env.python_path,
        "go_modcache": env.go_modcache,
        "go_modfile": env.go_modfile,
        "go_sumfile": env.go_sumfile,
        "node_modules": env.node_modules,
    }
    return env.profile_sha256, {key: str(value) for key, value in values.items() if value is not None}


def _install(profile: RuntimeProfile, locks: dict[str, Path], dest: Path) -> None:
    env = _resolver_env(dest)
    timeout = 300
    if profile.language == "python":
        tool = discover().python
        if not tool.ok or not tool.path:
            raise RuntimeProfileError("missing", "Python runtime unavailable")
        command = [tool.path, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
                   "--no-compile", "--no-deps", "--require-hashes",
                   "--index-url", "https://pypi.org/simple"]
        if not profile.allow_source:
            command.append("--only-binary=:all:")
        command.extend(["--target", str(dest / "site-packages"), "-r", str(locks["requirements.lock"])])
        proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=timeout)
    elif profile.language == "go":
        tool = discover().go
        if not tool.ok or not tool.path:
            raise RuntimeProfileError("missing", "Go runtime unavailable")
        shutil.copy2(locks["go.mod"], dest / "go.mod")
        shutil.copy2(locks["go.sum"], dest / "go.sum")
        module_cache = dest / "gomodcache"
        module_cache.mkdir()
        # Go 1.26 ignores a go.mod whose directory is TMPDIR. Keep the module
        # root and the temp directory separate.
        nested_tmp = dest / "tmp"
        nested_tmp.mkdir()
        env["TMP"] = env["TEMP"] = env["TMPDIR"] = str(nested_tmp)
        env.update({"GOMODCACHE": str(module_cache), "GOSUMDB": "sum.golang.org",
                    "GOTOOLCHAIN": "local", "GOPROXY": "https://proxy.golang.org"})
        proc = subprocess.run([tool.path, "mod", "download", "all"], cwd=dest,
                              env=env, capture_output=True, text=True, timeout=timeout)
    else:
        npm = which("npm")
        tools = discover()
        if not tools.node.ok or not tools.tsc.ok or not npm:
            raise RuntimeProfileError("missing", "Node, npm, or TypeScript compiler unavailable")
        shutil.copy2(locks["package.json"], dest / "package.json")
        shutil.copy2(locks["package-lock.json"], dest / "package-lock.json")
        proc = subprocess.run(
            [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--userconfig",
             str(dest / "resolver.npmrc"), "--registry=https://registry.npmjs.org"],
            cwd=dest, env=env, capture_output=True, text=True, timeout=timeout,
        )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "installer failed").strip()[-800:]
        raise RuntimeProfileError("error", detail)
    if profile.language == "go":
        if any(_file_hash(dest / name) != _file_hash(locks[name]) for name in ("go.mod", "go.sum")):
            raise RuntimeProfileError("error", "Go preparation changed the locked module files")
    if profile.language == "typescript":
        if any(_file_hash(dest / name) != _file_hash(locks[name])
               for name in ("package.json", "package-lock.json")):
            raise RuntimeProfileError("error", "npm preparation changed the locked package files")


def _validate_lock_contents(profile: RuntimeProfile, locks: dict[str, Path]) -> None:
    if profile.language == "python":
        try:
            requirement_lines = locks["requirements.lock"].read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise RuntimeProfileError("error", f"cannot read requirements.lock: {exc}") from exc
        for number, raw in enumerate(requirement_lines, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            pieces = line.split()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9.!+_-]*", pieces[0]):
                raise RuntimeProfileError("error", f"requirements.lock:{number} must pin a package version")
            hashes = [piece.removeprefix("--hash=sha256:") for piece in pieces[1:]
                      if piece.startswith("--hash=sha256:")]
            if len(hashes) != len(pieces) - 1 or not hashes or any(not _is_sha256(value) for value in hashes):
                raise RuntimeProfileError("error", f"requirements.lock:{number} requires SHA-256 hashes")
    elif profile.language == "typescript":
        try:
            lock = json.loads(locks["package-lock.json"].read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise RuntimeProfileError("error", f"invalid npm lockfile: {exc}") from exc
        for metadata in lock.get("packages", {}).values():
            resolved = metadata.get("resolved") if isinstance(metadata, dict) else None
            if resolved and not resolved.startswith("https://registry.npmjs.org/"):
                raise RuntimeProfileError("error", f"npm lockfile contains unapproved source: {resolved}")


def _resolver_env(temp_root: Path) -> dict[str, str]:
    home = temp_root / "resolver-home"
    home.mkdir(parents=True, exist_ok=True)
    appdata = temp_root / "resolver-appdata"
    appdata.mkdir(parents=True, exist_ok=True)
    npm_userconfig = temp_root / "resolver.npmrc"
    npm_userconfig.write_text("", encoding="utf-8")
    env = {
        "PATH": search_path(), "HOME": str(home), "USERPROFILE": str(home),
        "APPDATA": str(appdata), "LOCALAPPDATA": str(appdata),
        "TMP": str(temp_root), "TEMP": str(temp_root), "TMPDIR": str(temp_root),
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1",
        "npm_config_cache": str(temp_root / "npm-cache"), "npm_config_ignore_scripts": "true",
        "NPM_CONFIG_USERCONFIG": str(npm_userconfig), "GOTOOLCHAIN": "local",
    }
    for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _profile_hash(profile: RuntimeProfile) -> str:
    digest = hashlib.sha256(profile.id.encode())
    digest.update(profile.language.encode())
    for relative, expected in sorted(profile.lockfiles):
        digest.update(relative.encode())
        digest.update(expected.encode())
    digest.update(platform.system().encode())
    digest.update(platform.machine().encode())
    tools = discover()
    tool = {"python": tools.python, "go": tools.go, "typescript": tools.node}[profile.language]
    digest.update((tool.version or "missing").encode())
    if profile.language == "typescript":
        digest.update((tools.tsc.version or "missing").encode())
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _environment(profile: RuntimeProfile, digest: str, root: Path) -> RuntimeEnvironment:
    if profile.language == "python":
        return RuntimeEnvironment(profile.id, digest, profile.language, root,
                                  python_path=root / "site-packages")
    if profile.language == "go":
        return RuntimeEnvironment(profile.id, digest, profile.language, root,
                                  go_modcache=root / "gomodcache", go_modfile=root / "go.mod",
                                  go_sumfile=root / "go.sum")
    return RuntimeEnvironment(profile.id, digest, profile.language, root,
                              node_modules=root / "node_modules")
