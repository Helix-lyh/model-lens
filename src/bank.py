"""Module C：题库 20–60 题，按领域-难度编号；快速/全量选题不同。"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import yaml

from src.grade import attach_temperature, grade_response
from src.toolchain import CODE_LANGS
from src.types import BankResult, Difficulty, Question, QuestionResult, SampleGrade

DOMAINS = ("architecture", "coding", "knowledge", "reasoning")
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
QUESTION_ID_RE = re.compile(r"^(architecture|coding|knowledge|reasoning)-(easy|medium|hard)-(\d{2})$")
_LANG_HEAD = {
    "python": "只输出一个 python 代码块。不要解释。不要第三方库。",
    "go": "只输出一个 go 代码块。文件必须是 package solution。不要解释。不要第三方库。不要发起网络请求。",
    "typescript": "只输出一个 typescript 代码块。用 export 导出符号。不要解释。不要 npm 包。不要使用 fs/net。",
}
BANK_MIN = 20
BANK_MAX = 60
DEFAULT_CONCURRENCY = 4
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
    raw_questions = [_as_question(item) for item in raw]
    _validate_bank(raw_questions)
    questions: list[Question] = []
    for q in raw_questions:
        questions.extend(_expand_question(q))
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


def _expand_question(q: Question) -> list[Question]:
    gtype = str(q.grader.get("type") or "")
    if gtype != "code_tests":
        return [q]
    langs = q.grader.get("languages")
    if not isinstance(langs, dict) or not langs:
        raise ValueError(f"{q.id} 需要 grader.languages")
    unknown = [lang for lang in langs if lang not in CODE_LANGS]
    if unknown:
        raise ValueError(f"{q.id} 不支持的语言 {unknown}，只做 {', '.join(CODE_LANGS)}")
    missing = [lang for lang in CODE_LANGS if langs.get(lang) is None]
    if missing:
        raise ValueError(f"{q.id} 必须同时给出 {', '.join(CODE_LANGS)}，缺少 {missing}")
    out: list[Question] = []
    for lang in CODE_LANGS:
        spec = langs[lang]
        if not isinstance(spec, dict) or not spec.get("tests_file"):
            raise ValueError(f"{q.id} languages.{lang}.tests_file 缺失")
        out.append(_coding_variant(q, lang, spec))
    return out


def _coding_variant(q: Question, lang: str, spec: dict[str, Any]) -> Question:
    grader = {**q.grader, "type": "code_tests", "language": lang, "tests_file": spec["tests_file"]}
    grader.pop("languages", None)
    head = _LANG_HEAD[lang]
    sig = str(spec.get("signature") or "").strip()
    suffix = str(spec.get("prompt_suffix") or "").strip()
    extra = f"\n实现：{sig}" if sig else ""
    extra += f"\n{suffix}" if suffix else ""
    prompt = f"{head}\n\n{q.prompt.strip()}{extra}\n"
    return Question(
        id=f"{q.id}-{lang}",
        domain=q.domain,
        difficulty=q.difficulty,
        prompt=prompt,
        grader=grader,
        pass_criteria=q.pass_criteria,
        language=lang,
    )


def _validate_bank(questions: list[Question]) -> None:
    """校验展开前的原始题列表；编码题按 1 题计，不按语言展开后计数。"""
    ids: set[str] = set()
    for q in questions:
        if q.id in ids:
            raise ValueError(f"重复题 id: {q.id}")
        ids.add(q.id)
    n = len(questions)
    if not (BANK_MIN <= n <= BANK_MAX):
        raise ValueError(f"题库必须 {BANK_MIN}–{BANK_MAX} 题（展开前），当前 {n}")
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
    concurrency: int = DEFAULT_CONCURRENCY,
) -> BankResult:
    root = repo or repo_root()
    picked = select_questions(questions, "quick" if quick else "full")
    temps = [0.0] if quick else [0.0, 0.7, 0.7, 0.7]
    jobs = [(question, i, temp) for question in picked for i, temp in enumerate(temps)]
    graded = _run_jobs(
        jobs,
        client=client,
        salt=salt,
        root=root,
        kind_prefix=kind_prefix,
        stream_metrics=stream_metrics,
        concurrency=concurrency,
    )
    results = [
        _summarize_question(question, [graded[(question.id, i)] for i in range(len(temps))])
        for question in picked
    ]
    return _summarize_bank(results, salt=salt, quick=quick)


def _run_jobs(
    jobs: list[tuple[Question, int, float]],
    *,
    client: Any,
    salt: str,
    root: Path,
    kind_prefix: str,
    stream_metrics: bool,
    concurrency: int,
) -> dict[tuple[str, int], SampleGrade]:
    workers = max(1, int(concurrency))

    def _one(job: tuple[Question, int, float]) -> tuple[str, int, SampleGrade]:
        question, i, temp = job
        return question.id, i, _grade_one(
            client,
            question,
            salt=salt,
            root=root,
            kind_prefix=kind_prefix,
            stream_metrics=stream_metrics,
            temp=temp,
            sample_i=i,
        )

    if workers == 1 or len(jobs) <= 1:
        return {(qid, i): grade for qid, i, grade in (_one(job) for job in jobs)}
    graded: dict[tuple[str, int], SampleGrade] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for qid, i, grade in pool.map(_one, jobs):
            graded[(qid, i)] = grade
    return graded


def _grade_one(
    client: Any,
    question: Question,
    *,
    salt: str,
    root: Path,
    kind_prefix: str,
    stream_metrics: bool,
    temp: float,
    sample_i: int,
) -> SampleGrade:
    rec = client.complete(
        messages=[{"role": "user", "content": salt_prompt(question.prompt, salt)}],
        temperature=temp,
        max_tokens=None,
        kind=f"{kind_prefix}:{question.id}:t{temp}:n{sample_i}",
        stream=stream_metrics,
    )
    if rec.error is not None or rec.status_code is None or not (
        200 <= (rec.status_code or 0) < 300
    ):
        return SampleGrade(
            temperature=temp,
            status="missing",
            passed=None,
            detail=rec.error or f"http {rec.status_code}",
            content=rec.content,
            reasoning=rec.reasoning,
        )
    grade = grade_response(question, rec.content if isinstance(rec.content, str) else None, repo_root=root)
    attach_temperature(grade, temp)
    grade.reasoning = rec.reasoning
    _apply_think_penalty(grade, question, rec)
    return grade


def _apply_think_penalty(grade: SampleGrade, question: Question, rec: Any) -> SampleGrade:
    tokens = rec.completion_tokens
    if tokens is None or grade.score10 is None:
        return grade
    cap = THINK_LIMIT.get(question.difficulty, 100_000)
    if tokens <= cap:
        return grade
    grade.score10 = round(grade.score10 * 0.5, 2)
    if grade.points_total is not None:
        grade.points_total = grade.points_total * 2
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
    judged = [s for s in samples if s.passed is not None]
    if len(judged) < 3:
        return None
    return sum(1 for s in judged if s.passed is True) >= 3


def _group_stats(items: list[QuestionResult]) -> dict[str, Any]:
    judged = 0
    passed = 0
    missing = 0
    earned = 0
    total = 0
    score_sum = 0.0
    score_n = 0
    for q in items:
        if q.pass0 is None:
            missing += 1
        else:
            judged += 1
            if q.pass0:
                passed += 1
        if q.score10 is not None:
            score_sum += q.score10
            score_n += 1
        if q.samples:
            sample = q.samples[0]
            if sample.points is not None:
                earned += sample.points
            if sample.points_total is not None:
                total += sample.points_total
    return {
        "passed": passed,
        "judged": judged,
        "missing": missing,
        "earned": earned,
        "total": total,
        "score10": round(score_sum / score_n, 2) if score_n else None,
    }


def _summarize_bank(results: list[QuestionResult], *, salt: str, quick: bool) -> BankResult:
    domain_pass0: dict[str, dict[str, int]] = {}
    domain_points: dict[str, dict[str, float | int | None]] = {}
    for domain in DOMAINS:
        stats = _group_stats([q for q in results if q.domain == domain])
        domain_pass0[domain] = _pass_slice(stats)
        domain_points[domain] = _points_slice(stats)
    difficulty_points: dict[str, dict[str, float | int | None]] = {}
    for diff in DIFFICULTIES:
        stats = _group_stats([q for q in results if q.difficulty == diff])
        difficulty_points[str(diff)] = {
            "passed": stats["passed"],
            "judged": stats["judged"],
            **_points_slice(stats),
        }
    all_wrong, alarm = _knowledge_alarm(results)
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


def _pass_slice(stats: dict[str, Any]) -> dict[str, int]:
    return {
        "passed": stats["passed"],
        "judged": stats["judged"],
        "missing": stats["missing"],
    }


def _points_slice(stats: dict[str, Any]) -> dict[str, float | int | None]:
    return {
        "earned": stats["earned"],
        "total": stats["total"],
        "score10": stats["score10"],
    }


def _knowledge_alarm(results: list[QuestionResult]) -> tuple[bool, str | None]:
    knowledge = [q for q in results if q.domain == "knowledge"]
    judged_k = [q for q in knowledge if q.pass0 is not None]
    all_wrong = bool(judged_k) and all(q.pass0 is False for q in judged_k)
    alarm = "世界知识全错，像空响应或完全不对题" if all_wrong else None
    return all_wrong, alarm
