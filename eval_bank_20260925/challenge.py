"""Per-request prompt salt. The salt is not part of the question."""

from dataclasses import dataclass
import hashlib


@dataclass
class Challenge:
    id: str
    title: str
    kind: str
    prompt: str
    expected: dict
    scale: str
    level: str


def salt_prompt(prompt, salt):
    """Prefix a per-request nonce so a gateway cache cannot reuse a prior answer."""
    return f"【请求编号 {salt}；与题目无关】\n\n{prompt}"


def salted_prompt_hash(prompt):
    return hashlib.sha256(prompt.encode()).hexdigest()
