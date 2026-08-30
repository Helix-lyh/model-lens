from __future__ import annotations

from pathlib import Path

import pytest

from src.config import load_targets, resolve_api_key
from src.types import Endpoint


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_load_targets_omits_reference(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "targets.yaml",
        """
claimed_model: glm-5.3-flash
target:
  base_url: https://your-newapi/v1
  api_key_env: TARGET_KEY
  model: glm-5.3-flash
""",
    )
    targets = load_targets(path)
    assert targets.claimed_model == "glm-5.3-flash"
    assert targets.target.base_url == "https://your-newapi/v1"
    assert targets.target.api_key_env == "TARGET_KEY"
    assert targets.target.model == "glm-5.3-flash"
    assert targets.reference is None


def test_load_targets_includes_reference(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "targets.yaml",
        """
claimed_model: glm-5.3-flash
target:
  base_url: https://your-newapi/v1
  api_key_env: TARGET_KEY
  model: glm-5.3-flash
reference:
  base_url: https://official-or-trusted/v1
  api_key_env: REF_KEY
  model: glm-5.3-flash
""",
    )
    targets = load_targets(path)
    assert targets.reference is not None
    assert targets.reference.base_url == "https://official-or-trusted/v1"
    assert targets.reference.api_key_env == "REF_KEY"
    assert targets.reference.model == "glm-5.3-flash"


def test_load_targets_null_reference_is_omitted(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "targets.yaml",
        """
claimed_model: qwen
target:
  base_url: https://gw.example/v1
  api_key_env: TARGET_KEY
  model: qwen
reference: null
""",
    )
    assert load_targets(path).reference is None


def test_resolve_api_key_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_KEY", "only-in-memory")
    ep = Endpoint(
        base_url="https://your-newapi/v1",
        api_key_env="TARGET_KEY",
        model="glm-5.3-flash",
    )
    assert resolve_api_key(ep) == "only-in-memory"


def test_resolve_api_key_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARGET_KEY", raising=False)
    ep = Endpoint(
        base_url="https://your-newapi/v1",
        api_key_env="TARGET_KEY",
        model="glm-5.3-flash",
    )
    with pytest.raises(KeyError, match="TARGET_KEY"):
        resolve_api_key(ep)


def test_load_targets_official_channel_omits_base_url(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "targets.yaml",
        """
claimed_model: glm-4.5-flash
target:
  channel: zhipu
  api_key_env: ZHIPU_API_KEY
  model: glm-4.5-flash
""",
    )
    targets = load_targets(path)
    assert targets.target.channel == "zhipu"
    assert targets.target.base_url == ""
    assert targets.reference is None


def test_load_targets_bedrock_without_base_url(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "targets.yaml",
        """
claimed_model: claude
target:
  channel: bedrock
  api_key_env: AWS_BEARER_TOKEN_BEDROCK
  model: anthropic.claude-sonnet-4-20250514-v1:0
  compat:
    region: us-east-1
""",
    )
    targets = load_targets(path)
    assert targets.target.channel == "bedrock"
    assert targets.target.base_url == ""


def test_load_targets_unknown_channel(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "targets.yaml",
        """
claimed_model: x
target:
  channel: not-a-vendor
  api_key_env: TARGET_KEY
  model: x
""",
    )
    with pytest.raises(ValueError, match="未知 channel"):
        load_targets(path)


def test_resolve_api_key_empty_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_KEY", "   ")
    ep = Endpoint(
        base_url="https://your-newapi/v1",
        api_key_env="TARGET_KEY",
        model="demo",
    )
    with pytest.raises(KeyError, match="TARGET_KEY"):
        resolve_api_key(ep)
