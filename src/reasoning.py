"""从厂商响应里抽出思考链。只读已有字段，不本地编造。"""

from __future__ import annotations

from typing import Any


def extract_reasoning(data: object) -> str | None:
    if not isinstance(data, dict):
        return None
    chunks: list[str] = []
    _walk(data, chunks)
    text = "\n".join(part for part in chunks if part).strip()
    return text or None


def _walk(node: object, out: list[str]) -> None:
    if isinstance(node, dict):
        for key in ("reasoning_content", "reasoning", "thinking", "thought"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
        if node.get("type") in {"thinking", "reasoning"} and isinstance(node.get("text"), str):
            out.append(node["text"].strip())
        if node.get("thought") is True and isinstance(node.get("text"), str):
            out.append(node["text"].strip())
        for value in node.values():
            if isinstance(value, (dict, list)):
                _walk(value, out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, out)
