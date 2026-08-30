#!/usr/bin/env python3
"""下载 Phase 1 词表到 catalog/tokenizers/，按真实 sha256 写回 manifest。可重复执行。"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "catalog" / "manifest.json"
DEST_DIR = REPO_ROOT / "catalog" / "tokenizers"
TIMEOUT_S = 180
UA = "model-lens-catalog-fetch/0.1"
CHUNK = 64 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def looks_valid(backend: str, data: bytes) -> bool:
    head = data[:200].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        return False
    if backend in ("tokenizers", "tiktoken.tok.json"):
        return data.lstrip().startswith(b"{")
    if backend in ("tiktoken.model", "tiktoken.hunyuan"):
        return len(data) > 1000
    return True


def download(url: str, dest: Path, backend: str = "") -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        if getattr(resp, "status", 200) >= 400:
            raise RuntimeError(f"HTTP {resp.status}")
        with tempfile.NamedTemporaryFile(delete=False, dir=dest.parent) as tmp:
            tmp_path = Path(tmp.name)
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                tmp.write(chunk)
    try:
        data_head = tmp_path.read_bytes()[:4096]
        backend_hint = backend or ("tokenizers" if dest.suffix == ".json" else "tiktoken.model")
        if not looks_valid(backend_hint, data_head + b"\n"):
            full = tmp_path.read_bytes()
            if not looks_valid(backend_hint, full):
                raise RuntimeError("downloaded content is not a tokenizer file (got HTML or empty)")
        tmp_path.replace(dest)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(data: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    data = load_manifest()
    vocabs = data["vocabs"]
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0

    for entry in vocabs:
        vid = entry["id"]
        backend = entry.get("backend")
        url = entry.get("source_url")
        rel = entry.get("local_path")
        if backend == "tiktoken" and not rel:
            print(f"[skip] {vid}: tiktoken builtin")
            continue
        if not url or not rel:
            print(f"[skip] {vid}: no downloadable source")
            continue

        dest = REPO_ROOT / rel
        expected = entry.get("sha256")

        optional = bool(entry.get("optional"))
        if dest.is_file():
            actual = sha256_file(dest)
            if expected and actual == expected:
                print(f"[ok] {vid}: exists, sha256 match")
                entry["status"] = "ok"
                continue
            if expected is None:
                entry["sha256"] = actual
                entry["status"] = "ok"
                print(f"[hash] {vid}: existing file {actual} ({dest.stat().st_size} bytes)")
                continue
            print(f"[reget] {vid}: sha256 mismatch, re-download")

        print(f"[get] {vid}: {url}")
        try:
            download(url, dest, backend=str(backend or ""))
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            print(f"[fail] {vid}: {exc}", file=sys.stderr)
            entry["sha256"] = None
            entry["status"] = "optional" if optional else "missing"
            if not optional:
                failed += 1
            continue

        actual = sha256_file(dest)
        entry["sha256"] = actual
        entry["status"] = "ok"
        print(f"[ok] {vid}: {actual} ({dest.stat().st_size} bytes)")

    save_manifest(data)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
