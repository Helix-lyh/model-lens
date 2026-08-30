"""共享数据类型。实现模块只按这些结构互相对接。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable


FamilyStatus = Literal["ok", "ambiguous", "token_untrusted"]
Confidence = Literal["high", "medium", "low"]
IdentityStatus = Literal["不支持", "同族未分型", "skipped", "invalid"]
DegradeStatus = Literal["疑似衰减", "未检出衰减", "偏离不足以下结论", "skipped"]


@dataclass(frozen=True)
class Endpoint:
    """一条待测 / 参考源。channel 选官方预设；api 选线协议。均可省略。"""

    base_url: str
    api_key_env: str
    model: str
    channel: str | None = None
    api: str | None = None
    api_version: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    compat: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Targets:
    claimed_model: str
    target: Endpoint
    reference: Endpoint | None = None


@dataclass
class CompletionRecord:
    """一次调用的落盘记录。密钥不得写入。"""

    kind: str
    endpoint: str
    model: str
    request: dict[str, Any]
    status_code: int | None
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    content: str | None
    reasoning: str | None = None
    raw: Any = None
    error: str | None = None
    channel: str | None = None
    api: str | None = None
    usage: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class Probe:
    id: str
    text: str
    escaped: bool = False


@dataclass
class ProbeDelta:
    probe_id: str
    text: str
    escaped: bool
    prompt_tokens_base: int | None
    prompt_tokens_probe: int | None
    delta_api: int | None
    dropped: bool
    drop_reason: str | None = None
    n_hat: dict[str, int] = field(default_factory=dict)


@dataclass
class FamilyScore:
    catalog_id: str
    exact_hits: int
    l1: int
    n_used: int


@dataclass
class FamilyResult:
    status: FamilyStatus
    family: str
    confidence: Confidence | None
    hits: int
    n_probes: int
    l1: int | None
    runner_up: str | None
    runner_up_hits: int | None
    runner_up_l1: int | None
    scores: list[FamilyScore] = field(default_factory=list)
    probes: list[ProbeDelta] = field(default_factory=list)
    untrusted_reason: str | None = None


class Vocab(Protocol):
    id: str

    def encode_len(self, text: str, *, escaped: bool = False) -> int: ...

    def n_hat(self, base: str, probe: str, *, escaped: bool = False) -> int: ...


GradeStatus = Literal["pass", "fail", "missing", "error"]
DomainName = Literal["architecture", "coding", "knowledge", "reasoning"]
Difficulty = Literal["easy", "medium", "hard"]


@dataclass(frozen=True)
class Question:
    id: str
    domain: DomainName
    difficulty: Difficulty
    prompt: str
    grader: dict[str, Any]
    pass_criteria: str
    language: str | None = None


@dataclass
class SampleGrade:
    temperature: float
    status: GradeStatus
    passed: bool | None
    detail: str
    content: str | None = None
    reasoning: str | None = None
    points: int | None = None
    points_total: int | None = None
    score10: float | None = None


@dataclass
class QuestionResult:
    question_id: str
    domain: DomainName
    difficulty: Difficulty | None = None
    samples: list[SampleGrade] = field(default_factory=list)
    pass0: bool | None = None
    majority: bool | None = None
    score10: float | None = None


@dataclass
class BankResult:
    quick: bool
    salt: str
    questions: list[QuestionResult] = field(default_factory=list)
    domain_pass0: dict[str, dict[str, int]] = field(default_factory=dict)
    domain_points: dict[str, dict[str, float | int | None]] = field(default_factory=dict)
    difficulty_points: dict[str, dict[str, float | int | None]] = field(default_factory=dict)
    knowledge_all_wrong: bool = False
    knowledge_alarm: str | None = None
    n_questions: int = 0


@dataclass
class IdentityResult:
    status: IdentityStatus
    claimed_family: str | None
    observed_family: str | None
    confidence_used: Confidence | None
    note: str
    coding_agree: dict[str, Any] | None = None


@dataclass
class DegradeResult:
    status: DegradeStatus
    pass0_target: float | None
    pass0_ref: float | None
    stab_target: float | None
    stab_ref: float | None
    pass0_delta: float | None
    stab_delta: float | None
    note: str
    score10_target: float | None = None
    score10_ref: float | None = None
    score10_delta: float | None = None


class Recorder(Protocol):
    path: Path

    def write(self, record: CompletionRecord) -> None: ...


@runtime_checkable
class Completer(Protocol):
    """family / 题库共用的 complete 入口。ChatClient 与测试 FakeClient 都实现它。"""

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        extra: dict | None = None,
        kind: str = "chat",
        stream: bool = False,
    ) -> CompletionRecord: ...
