"""Module C：题库 20–60 题，按领域-难度编号；快速/全量选题不同。"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import yaml

from src.grade import attach_temperature, grade_response
from src.types import BankResult, Difficulty, Question, QuestionResult, SampleGrade

DOMAINS = ("architecture", "coding", "knowledge")
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
QUESTION_ID_RE = re.compile(r"^(architecture|coding|knowledge)-(easy|medium|hard)-(\d{2})$")
BANK_MIN = 20
BANK_MAX = 60
QUICK_DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium")
THINK_LIMIT = {"easy": 80_000, "medium": 100_000, "hard": 128_000}
BankMode = Literal["quick", "full"]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_questions(root: Path | None = None, *, mode: BankMode | None = None) -> list[Question]:
    root = root or repo_root()
    raw = yaml.safe_load((root / "bank" / "questions.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("bank/questions.yaml 必须是题列表")
    questions = [_as_question(item) for item in raw]
    _validate_bank(questions)
    return select_questions(questions, mode) if mode else questions


def select_questions(questions: list[Question], mode: BankMode | None) -> list[Question]:
    if mode == "quick":
        return [q for q in questions if q.difficulty in QUICK_DIFFICULTIES]
    return list(questions)


def _as_question(item: object) -> Question:
    if not isinstance(item, dict):
        raise ValueError("question 必须是映射")
    domain = item["domain"]
    if domain not in DOMAINS:
        raise ValueError(f"未知 domain: {domain}")
    difficulty = str(item["difficulty"])
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"difficulty 必须是 easy/medium/hard，当前 {difficulty}")
    qid = str(item["id"])
    parsed = QUESTION_ID_RE.fullmatch(qid)
    if not parsed:
        raise ValueError(f"题号必须是 domain-difficulty-序号，例如 coding-medium-01，当前 {qid}")
    id_domain, id_diff, _seq = parsed.groups()
    if id_domain != domain:
        raise ValueError(f"{qid} 的领域段与 domain={domain} 不一致")
    if id_diff != difficulty:
        raise ValueError(f"{qid} 的难度段与 difficulty={difficulty} 不一致")
    return Question(
        id=qid,
        domain=domain,
        difficulty=difficulty,  # type: ignore[arg-type]
        prompt=str(item["prompt"]),
        grader=dict(item.get("grader") or {}),
        pass_criteria=str(item.get("pass_criteria") or ""),
    )


def _validate_bank(questions: list[Question]) -> None:
    ids: set[str] = set()
    for q in questions:
        if q.id in ids:
            raise ValueError(f"重复题 id: {q.id}")
        ids.add(q.id)
    n = len(questions)
    if not (BANK_MIN <= n <= BANK_MAX):
        raise ValueError(f"题库必须 {BANK_MIN}–{BANK_MAX} 题，当前 {n}")
    for domain in DOMAINS:
        have = {q.difficulty for q in questions if q.domain == domain}
        missing = [d for d in DIFFICULTIES if d not in have]
        if missing:
            raise ValueError(f"{domain} 缺少难度 {missing}")
    if not select_questions(questions, "quick"):
        raise ValueError("快速模式没有题目（需要 easy 或 medium）")


def salt_prompt(prompt: str, salt: str) -> str:
    return f"【审计标记 {salt} 与本题答案无关】\n\n{prompt}"


def run_bank(
    client: Any,
    questions: list[Question],
    *,
    salt: str,
    quick: bool = False,
    repo: Path | None = None,
    kind_prefix: str = "bank",
    stream_metrics: bool = False,
) -> BankResult:
    root = repo or repo_root()
    picked = select_questions(questions, "quick" if quick else "full")
    temps = [0.0] if quick else [0.0, 0.7, 0.7, 0.7]
    results: list[QuestionResult] = []
    for question in picked:
        samples: list[SampleGrade] = []
        for i, temp in enumerate(temps):
            rec = client.complete(
                messages=[{"role": "user", "content": salt_prompt(question.prompt, salt)}],
                temperature=temp,
                max_tokens=None,
                kind=f"{kind_prefix}:{question.id}:t{temp}:n{i}",
                stream=stream_metrics,
            )
            content = rec.content if rec.error is None else None
            if rec.error is not None or rec.status_code is None or not (
                200 <= (rec.status_code or 0) < 300
            ):
                grade = SampleGrade(
                    temperature=temp,
                    status="missing",
                    passed=None,
                    detail=rec.error or f"http {rec.status_code}",
                    content=rec.content,
                    reasoning=rec.reasoning,
                )
            else:
                grade = grade_response(question, content, repo_root=root)
                attach_temperature(grade, temp)
                grade.reasoning = rec.reasoning
                _apply_think_penalty(grade, question, rec)
            samples.append(grade)
        results.append(_summarize_question(question, samples))
    return _summarize_bank(results, salt=salt, quick=quick)


def _apply_think_penalty(grade: SampleGrade, question: Question, rec: Any) -> SampleGrade:
    tokens = rec.completion_tokens
    if tokens is None or grade.score10 is None:
        return grade
    cap = THINK_LIMIT.get(question.difficulty, 100_000)
    if tokens <= cap:
        return grade
    grade.score10 = round(grade.score10 * 0.5, 2)
    grade.detail = f"{grade.detail} think_penalty tokens={tokens}>{cap}"
    return grade


def _summarize_question(question: Question, samples: list[SampleGrade]) -> QuestionResult:
    pass0 = samples[0].passed if samples else None
    majority = _majority(samples)
    return QuestionResult(
        question_id=question.id,
        domain=question.domain,
        difficulty=question.difficulty,
        samples=samples,
        pass0=pass0,
        majority=majority,
        score10=samples[0].score10 if samples else None,
    )


def _majority(samples: list[SampleGrade]) -> bool | None:
    if len(samples) < 4:
        return None
    wins = sum(1 for s in samples if s.passed is True)
    return True if wins >= 3 else False


def _summarize_bank(results: list[QuestionResult], *, salt: str, quick: bool) -> BankResult:
    domain_pass0: dict[str, dict[str, int]] = {}
    domain_points: dict[str, dict[str, float | int | None]] = {}
    for domain in DOMAINS:
        items = [q for q in results if q.domain == domain]
        judged = [q for q in items if q.pass0 is not None]
        passed = [q for q in judged if q.pass0]
        earned = sum(s.points or 0 for q in items for s in q.samples[:1] if s.points is not None)
        total = sum(s.points_total or 0 for q in items for s in q.samples[:1] if s.points_total is not None)
        scores = [q.score10 for q in items if q.score10 is not None]
        domain_pass0[domain] = {
            "passed": len(passed),
            "judged": len(judged),
            "missing": sum(1 for q in items if q.pass0 is None),
        }
        domain_points[domain] = {
            "earned": earned,
            "total": total,
            "score10": round(sum(scores) / len(scores), 2) if scores else None,
        }
    difficulty_points: dict[str, dict[str, float | int | None]] = {}
    for diff in DIFFICULTIES:
        items = [q for q in results if q.difficulty == diff]
        earned = sum(s.points or 0 for q in items for s in q.samples[:1] if s.points is not None)
        total = sum(s.points_total or 0 for q in items for s in q.samples[:1] if s.points_total is not None)
        scores = [q.score10 for q in items if q.score10 is not None]
        judged = [q for q in items if q.pass0 is not None]
        passed = [q for q in judged if q.pass0]
        difficulty_points[str(diff)] = {
            "passed": len(passed),
            "judged": len(judged),
            "earned": earned,
            "total": total,
            "score10": round(sum(scores) / len(scores), 2) if scores else None,
        }
    knowledge = [q for q in results if q.domain == "knowledge"]
    judged_k = [q for q in knowledge if q.pass0 is not None]
    all_wrong = bool(judged_k) and all(q.pass0 is False for q in judged_k)
    alarm = "世界知识全错，像空响应或完全不对题" if all_wrong else None
    return BankResult(
        quick=quick,
        salt=salt,
        questions=results,
        domain_pass0=domain_pass0,
        domain_points=domain_points,
        difficulty_points=difficulty_points,
        knowledge_all_wrong=all_wrong,
        knowledge_alarm=alarm,
        n_questions=len(results),
    )


def bank_asdict(result: BankResult) -> dict[str, Any]:
    return asdict(result)
