"""Module C：50 条 raw 题，按领域-难度编号；快速/全量选题不同。"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import yaml

from src.fixtures import resolve_fixture_path
from src.grade import attach_temperature, grade_response
from src.toolchain import CODE_LANGS
from src.types import BankResult, Difficulty, Question, QuestionResult, SampleGrade

DOMAINS = ("architecture", "coding", "knowledge", "reasoning")
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard", "extreme")
QUESTION_ID_RE = re.compile(
    r"^(architecture|coding|knowledge|reasoning)-(easy|medium|hard|extreme)-(\d{2})$"
)
_LANG_HEAD = {
    "python": "只输出一个 python 代码块。不要解释。不要第三方库。",
    "go": "只输出一个 go 代码块。文件必须是 package solution。不要解释。不要第三方库。不要发起网络请求。",
    "typescript": "只输出一个 typescript 代码块。用 export 导出符号。不要解释。不要 npm 包。不要使用 fs/net。",
}
BANK_MIN = 20
BANK_MAX = 60
BANK_RAW_COUNT = 50
BANK_EXPANDED_COUNT = 74
BANK_QUICK_COUNT = 14
DEFAULT_CONCURRENCY = 4
QUICK_DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium")
THINK_LIMIT = {"easy": 80_000, "medium": 100_000, "hard": 128_000, "extreme": 160_000}
RAW_MATRIX: dict[str, dict[str, int]] = {
    "architecture": {"easy": 1, "medium": 1, "hard": 5, "extreme": 5},
    "coding": {"easy": 1, "medium": 1, "hard": 5, "extreme": 5},
    "knowledge": {"easy": 1, "medium": 1, "hard": 5, "extreme": 5},
    "reasoning": {"easy": 2, "medium": 2, "hard": 5, "extreme": 5},
}
_ALLOWED_GRADERS = frozenset({"alias", "keyword", "structure", "code_tests"})
BankMode = Literal["quick", "full"]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_questions(root: Path | None = None, *, mode: BankMode | None = None) -> list[Question]:
    root = root or repo_root()
    raw = yaml.safe_load((root / "bank" / "questions.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("bank/questions.yaml 必须是题列表")
    raw_questions = [_as_question(item, root=root) for item in raw]
    _validate_bank(raw_questions, root=root)
    questions: list[Question] = []
    for q in raw_questions:
        questions.extend(_expand_question(q, root=root))
    if len(questions) != BANK_EXPANDED_COUNT:
        raise ValueError(f"题库展开后必须 {BANK_EXPANDED_COUNT} 题，当前 {len(questions)}")
    selected = select_questions(questions, mode)
    if mode == "quick" and len(selected) != BANK_QUICK_COUNT:
        raise ValueError(f"快速题库必须 {BANK_QUICK_COUNT} 个展开实例，当前 {len(selected)}")
    return selected if mode else questions


def select_questions(questions: list[Question], mode: BankMode | None) -> list[Question]:
    if mode == "quick":
        return [q for q in questions if q.difficulty in QUICK_DIFFICULTIES]
    return list(questions)


def _as_question(item: object, *, root: Path | None = None) -> Question:
    if not isinstance(item, dict):
        raise ValueError("question 必须是映射")
    for key in ("domain", "difficulty", "id", "prompt"):
        if key not in item:
            raise ValueError(f"question 缺少字段 {key}")
    domain = item["domain"]
    if domain not in DOMAINS:
        raise ValueError(f"未知 domain: {domain}")
    difficulty = str(item["difficulty"])
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"difficulty 必须是 easy/medium/hard/extreme，当前 {difficulty}")
    qid = str(item["id"])
    parsed = QUESTION_ID_RE.fullmatch(qid)
    if not parsed:
        raise ValueError(f"题号必须是 domain-difficulty-序号，例如 coding-medium-01，当前 {qid}")
    id_domain, id_diff, _seq = parsed.groups()
    if id_domain != domain:
        raise ValueError(f"{qid} 的领域段与 domain={domain} 不一致")
    if id_diff != difficulty:
        raise ValueError(f"{qid} 的难度段与 difficulty={difficulty} 不一致")
    prompt = str(item["prompt"]).strip()
    if not prompt:
        raise ValueError(f"{qid} prompt 不能为空")
    grader = item.get("grader")
    if not isinstance(grader, dict):
        raise ValueError(f"{qid} grader 必须是映射")
    pass_criteria = str(item.get("pass_criteria") or "").strip()
    if not pass_criteria:
        raise ValueError(f"{qid} pass_criteria 不能为空")
    q = Question(
        id=qid,
        domain=domain,
        difficulty=difficulty,  # type: ignore[arg-type]
        prompt=prompt + "\n",
        grader=dict(grader),
        pass_criteria=pass_criteria,
        raw_id=qid,
        cluster_id=qid,
    )
    _validate_grader(q, root=root or repo_root())
    return q


def _expand_question(q: Question, *, root: Path | None = None) -> list[Question]:
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
        raw_id=q.raw_id or q.id,
        cluster_id=q.cluster_id or q.id,
    )


def _validate_bank(questions: list[Question], *, root: Path | None = None) -> None:
    """校验展开前的活动题库；编码题按 1 个 raw cluster 计数。"""
    ids: set[str] = set()
    for q in questions:
        if q.id in ids:
            raise ValueError(f"重复题 id: {q.id}")
        ids.add(q.id)
        _validate_grader(q, root=root or repo_root())
    n = len(questions)
    if not (BANK_MIN <= n <= BANK_MAX):
        raise ValueError(f"题库必须 {BANK_MIN}–{BANK_MAX} 题（展开前），当前 {n}")
    if n != BANK_RAW_COUNT:
        raise ValueError(f"活动题库必须 {BANK_RAW_COUNT} 条 raw 题，当前 {n}")
    counts = {domain: {diff: 0 for diff in DIFFICULTIES} for domain in DOMAINS}
    for q in questions:
        counts[q.domain][q.difficulty] += 1
    expected_global = {diff: sum(row[diff] for row in RAW_MATRIX.values()) for diff in DIFFICULTIES}
    actual_global = {diff: sum(row[diff] for row in counts.values()) for diff in DIFFICULTIES}
    if actual_global != expected_global:
        raise ValueError(f"难度数量必须为 {expected_global}，当前 {actual_global}")
    for domain in DOMAINS:
        actual = counts[domain]
        if actual != RAW_MATRIX[domain]:
            raise ValueError(f"{domain} 难度矩阵必须为 {RAW_MATRIX[domain]}，当前 {actual}")
    if not select_questions(questions, "quick"):
        raise ValueError("快速模式没有题目（需要 easy 或 medium）")
    if sum(1 for q in questions if q.domain == "coding") != 12:
        raise ValueError("coding 必须有 12 个 raw cluster")


def _validate_grader(question: Question, *, root: Path) -> None:
    grader = question.grader
    gtype = grader.get("type")
    if gtype not in _ALLOWED_GRADERS:
        raise ValueError(f"{question.id} 未知 grader {gtype!r}")
    if gtype == "alias":
        answers = grader.get("answers")
        match = grader.get("match", "contains")
        if match not in {"exact", "contains"} or not isinstance(answers, list) or not answers:
            raise ValueError(f"{question.id} alias 必须有非空 answers 且 match 为 exact/contains")
        if any(not isinstance(answer, str) or not answer.strip() for answer in answers):
            raise ValueError(f"{question.id} alias.answers 只能是非空字符串")
    elif gtype == "keyword":
        groups = grader.get("must_include")
        min_hits = grader.get("min_hits")
        if not isinstance(groups, list) or not groups or not isinstance(min_hits, int):
            raise ValueError(f"{question.id} keyword 缺少 must_include/min_hits")
        if min_hits < 1 or min_hits > len(groups):
            raise ValueError(f"{question.id} keyword.min_hits 越界")
        if any(not (isinstance(g, str) or (isinstance(g, list) and g)) for g in groups):
            raise ValueError(f"{question.id} keyword groups 非法")
    elif gtype == "structure":
        _validate_fixture_path(grader.get("tests_file"), root=root, question_id=question.id)
    elif gtype == "code_tests":
        languages = grader.get("languages")
        if not isinstance(languages, dict) or set(languages) != set(CODE_LANGS):
            raise ValueError(f"{question.id} code_tests 必须同时提供 {', '.join(CODE_LANGS)}")
        for lang in CODE_LANGS:
            spec = languages[lang]
            if not isinstance(spec, dict) or not str(spec.get("signature") or "").strip():
                raise ValueError(f"{question.id} languages.{lang}.signature 缺失")
            _validate_fixture_path(spec.get("tests_file"), root=root, question_id=question.id)


def _validate_fixture_path(rel: object, *, root: Path, question_id: str = "") -> str:
    return str(resolve_fixture_path(root, rel, question_id=question_id))


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
    if rec.error is not None or rec.status_code is None or not (200 <= (rec.status_code or 0) < 300):
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
    raw_id = question.raw_id or (question.id.rsplit("-", 1)[0] if question.language else question.id)
    return QuestionResult(
        question_id=question.id,
        domain=question.domain,
        difficulty=question.difficulty,
        samples=samples,
        pass0=samples[0].passed if samples else None,
        majority=_majority(samples),
        score10=samples[0].score10 if samples else None,
        raw_id=raw_id,
        cluster_id=question.cluster_id or raw_id,
        language=question.language,
    )


def _majority(samples: list[SampleGrade]) -> bool | None:
    judged = [s for s in samples if s.passed is not None]
    if len(judged) < 3:
        return None
    return sum(1 for s in judged if s.passed is True) >= 3


def _raw_id(item: QuestionResult) -> str:
    explicit = item.raw_id or item.cluster_id
    if explicit:
        return str(explicit)
    lang = _language(item)
    return item.question_id.rsplit("-", 1)[0] if lang else item.question_id


def _language(item: QuestionResult) -> str | None:
    if item.language:
        return item.language
    for lang in CODE_LANGS:
        if item.question_id.endswith(f"-{lang}"):
            return lang
    return None


def _cluster_id(item: QuestionResult) -> str:
    if item.cluster_id or item.raw_id:
        return str(item.cluster_id or item.raw_id)
    lang = _language(item)
    return item.question_id.rsplit("-", 1)[0] if lang else item.question_id


def _cluster_rows(items: list[QuestionResult]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    grouped: dict[str, list[QuestionResult]] = {}
    for item in items:
        grouped.setdefault(_cluster_id(item), []).append(item)

    rows: list[dict[str, Any]] = []
    diagnostics: dict[str, dict[str, Any]] = {}
    for cluster, variants in grouped.items():
        if variants[0].domain != "coding":
            item = variants[0]
            sample = item.samples[0] if item.samples else None
            rows.append(
                {
                    "pass0": item.pass0,
                    "majority": item.majority,
                    "score10": item.score10,
                    "points": sample.points if sample else None,
                    "points_total": sample.points_total if sample else None,
                    "strict_complete": True,
                }
            )
            continue

        by_language = {_language(item) or item.question_id: item for item in variants}
        available = [item for item in variants if item.pass0 is not None]
        strict_complete = all(
            lang in by_language and by_language[lang].pass0 is not None
            for lang in CODE_LANGS
        )
        strict_pass0 = (
            all(by_language[lang].pass0 is True for lang in CODE_LANGS)
            if strict_complete
            else None
        )
        pass0 = None if not available else all(item.pass0 is True for item in available)
        majority_values = [item.majority for item in variants if item.majority is not None]
        scores = [item.score10 for item in available if item.score10 is not None]
        point_pairs = [
            (item.samples[0].points, item.samples[0].points_total)
            for item in available
            if item.samples
            and item.samples[0].points is not None
            and item.samples[0].points_total is not None
        ]
        strict_score_values = (
            [by_language[lang].score10 for lang in CODE_LANGS]
            if strict_complete
            else []
        )
        strict_scores = (
            [float(value) for value in strict_score_values if value is not None]
            if len(strict_score_values) == len(CODE_LANGS)
            and all(value is not None for value in strict_score_values)
            else []
        )
        strict_pair_values = (
            [
                (
                    by_language[lang].samples[0].points,
                    by_language[lang].samples[0].points_total,
                )
                if by_language[lang].samples
                else (None, None)
                for lang in CODE_LANGS
            ]
            if strict_complete
            else []
        )
        strict_pairs = (
            [(float(points), float(total)) for points, total in strict_pair_values]
            if len(strict_pair_values) == len(CODE_LANGS)
            and all(points is not None and total is not None for points, total in strict_pair_values)
            else []
        )
        rows.append(
            {
                "pass0": pass0,
                "majority": None if not majority_values else all(value is True for value in majority_values),
                "strict_pass0": strict_pass0,
                "score10": round(sum(scores) / len(scores), 2) if scores else None,
                "points": round(sum(p for p, _ in point_pairs) / len(point_pairs), 2) if point_pairs else None,
                "points_total": round(sum(t for _, t in point_pairs) / len(point_pairs), 2) if point_pairs else None,
                "strict_score10": round(sum(strict_scores) / len(strict_scores), 2) if strict_scores else None,
                "strict_points": round(sum(p for p, _ in strict_pairs) / len(strict_pairs), 2) if strict_pairs else None,
                "strict_points_total": round(sum(t for _, t in strict_pairs) / len(strict_pairs), 2) if strict_pairs else None,
                "strict_complete": strict_complete,
            }
        )
        diagnostics[cluster] = {
            "available_languages": [
                lang for lang in CODE_LANGS
                if lang in by_language and by_language[lang].pass0 is not None
            ],
            "missing_languages": [
                lang for lang in CODE_LANGS
                if lang not in by_language or by_language[lang].pass0 is None
            ],
            "strict_complete": strict_complete,
            "strict_pass0": strict_pass0,
            "available_pass": pass0,
            "languages": {
                lang: {
                    "pass0": by_language[lang].pass0,
                    "majority": by_language[lang].majority,
                    "score10": by_language[lang].score10,
                    "points": by_language[lang].samples[0].points if by_language[lang].samples else None,
                    "points_total": by_language[lang].samples[0].points_total if by_language[lang].samples else None,
                    "status": by_language[lang].samples[0].status if by_language[lang].samples else None,
                }
                for lang in CODE_LANGS
                if lang in by_language
            },
        }
    return rows, diagnostics


def _group_stats(items: list[QuestionResult], *, strict_coding: bool = False) -> dict[str, Any]:
    rows, _diagnostics = _cluster_rows(items)
    judged = passed = missing = 0
    earned = total = 0.0
    scores: list[float] = []
    strict = strict_coding and bool(items) and items[0].domain == "coding"
    for row in rows:
        pass0 = row["strict_pass0"] if strict else row["pass0"]
        if pass0 is None:
            missing += 1
        else:
            judged += 1
            if pass0:
                passed += 1
        score10 = row.get("strict_score10") if strict else row.get("score10")
        points = row.get("strict_points") if strict else row.get("points")
        points_total = row.get("strict_points_total") if strict else row.get("points_total")
        if score10 is not None:
            scores.append(float(score10))
        if points is not None and points_total is not None:
            # Language variants are averaged inside a cluster; keep fractional values.
            earned += points
            total += points_total
    return {
        "passed": passed,
        "judged": judged,
        "missing": missing,
        "earned": earned,
        "total": total,
        "score10": round(sum(scores) / len(scores), 2) if scores else None,
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
    raw_seen: dict[str, QuestionResult] = {}
    for q in results:
        raw_seen.setdefault(_raw_id(q), q)
    raw_domain_counts = {domain: sum(1 for q in raw_seen.values() if q.domain == domain) for domain in DOMAINS}
    raw_difficulty_counts = {
        diff: sum(1 for q in raw_seen.values() if q.difficulty == diff) for diff in DIFFICULTIES
    }
    expanded_domain_counts = {domain: sum(1 for q in results if q.domain == domain) for domain in DOMAINS}
    expanded_difficulty_counts = {
        diff: sum(1 for q in results if q.difficulty == diff) for diff in DIFFICULTIES
    }
    coding_clusters = {_cluster_id(q) for q in results if q.domain == "coding"}
    coding_items = [q for q in results if q.domain == "coding"]
    _coding_rows, coding_diagnostics = _cluster_rows(coding_items)
    available_stats = _group_stats(coding_items)
    strict_stats = _group_stats(coding_items, strict_coding=True)
    raw_matrix = {
        domain: {
            diff: sum(
                1
                for q in raw_seen.values()
                if q.domain == domain and q.difficulty == diff
            )
            for diff in DIFFICULTIES
        }
        for domain in DOMAINS
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
        raw_question_count=len(raw_seen),
        expanded_question_count=len(results),
        raw_domain_counts=raw_domain_counts,
        raw_difficulty_counts=raw_difficulty_counts,
        expanded_domain_counts=expanded_domain_counts,
        expanded_difficulty_counts=expanded_difficulty_counts,
        coding_cluster_count=len(coding_clusters),
        coding_variant_count=sum(1 for q in results if q.domain == "coding" and q.language),
        coding_available=_coding_summary(available_stats),
        coding_strict=_coding_summary(strict_stats),
        raw_matrix=raw_matrix,
        coding_cluster_diagnostics=coding_diagnostics,
    )


def _coding_summary(stats: dict[str, Any]) -> dict[str, int | float | None]:
    rate = stats["passed"] / stats["judged"] if stats["judged"] else None
    return {
        "passed": stats["passed"],
        "judged": stats["judged"],
        "missing": stats["missing"],
        "rate": round(rate, 4) if rate is not None else None,
    }


def _pass_slice(stats: dict[str, Any]) -> dict[str, int]:
    return {"passed": stats["passed"], "judged": stats["judged"], "missing": stats["missing"]}


def _points_slice(stats: dict[str, Any]) -> dict[str, float | int | None]:
    return {"earned": stats["earned"], "total": stats["total"], "score10": stats["score10"]}


def _knowledge_alarm(results: list[QuestionResult]) -> tuple[bool, str | None]:
    knowledge = [q for q in results if q.domain == "knowledge"]
    judged_k = [q for q in knowledge if q.pass0 is not None]
    all_wrong = bool(judged_k) and all(q.pass0 is False for q in judged_k)
    alarm = "世界知识全错，像空响应或完全不对题" if all_wrong else None
    return all_wrong, alarm
