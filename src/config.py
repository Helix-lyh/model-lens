"""加载 targets.yaml，并从环境变量解析密钥（密钥不落盘）。"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from src.channels.resolve import resolve_channel
from src.types import Endpoint, Targets


def _as_str_dict(value: object, *, field: str, path: Path) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{path}: {field} 必须是映射")
    return {str(k): str(v) for k, v in value.items()}


def _as_compat(value: object, *, field: str, path: Path) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{path}: {field} 必须是映射")
    return dict(value)


def _as_endpoint(data: object, *, field: str, path: Path) -> Endpoint:
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: {field} 必须是映射，含 api_key_env / model；"
            "base_url 可省略当 channel 带默认根路径"
        )
    try:
        api_key_env = str(data["api_key_env"])
        model = str(data["model"])
    except KeyError as exc:
        raise ValueError(f"{path}: {field} 缺少字段 {exc.args[0]}") from exc
    return Endpoint(
        base_url=str(data["base_url"]) if data.get("base_url") else "",
        api_key_env=api_key_env,
        model=model,
        channel=str(data["channel"]) if data.get("channel") else None,
        api=str(data["api"]) if data.get("api") else None,
        api_version=str(data["api_version"]) if data.get("api_version") else None,
        extra_headers=_as_str_dict(data.get("headers"), field=f"{field}.headers", path=path),
        compat=_as_compat(data.get("compat"), field=f"{field}.compat", path=path),
    )


def load_targets(path: str | Path) -> Targets:
    """读取 design.md §6 形状的 targets.yaml。reference 可省略。"""
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: 根节点必须是映射")
    if "claimed_model" not in data:
        raise ValueError(f"{path}: 缺少 claimed_model")
    if "target" not in data:
        raise ValueError(f"{path}: 缺少 target")

    reference: Endpoint | None = None
    raw_ref = data.get("reference")
    if raw_ref:
        reference = _as_endpoint(raw_ref, field="reference", path=path)

    target = _as_endpoint(data["target"], field="target", path=path)
    try:
        resolve_channel(target)
        if reference is not None:
            resolve_channel(reference)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc

    return Targets(
        claimed_model=str(data["claimed_model"]),
        target=target,
        reference=reference,
    )


def resolve_api_key(endpoint: Endpoint) -> str:
    """读取 os.environ[api_key_env]。缺失或空值时给出清晰错误，不回退。"""
    name = endpoint.api_key_env
    try:
        value = os.environ[name]
    except KeyError:
        raise KeyError(
            f"环境变量 {name} 未设置，无法请求 {endpoint.model} @ {endpoint.base_url}"
        ) from None
    if not value.strip():
        raise KeyError(
            f"环境变量 {name} 为空，无法请求 {endpoint.model} @ {endpoint.base_url}"
        )
    return value
