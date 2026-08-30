"""Module C 评分：关键词 / 别名 / 抽代码 / 结构遵循。不用 LLM-as-judge。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from src.types import GradeStatus, Question, SampleGrade

_FENCE = re.compile(
    r"```(?:python|py)\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_FENCE_ANY = re.compile(r"```\s*\n(.*?)```", re.DOTALL)
_PUNCT = dict.fromkeys(map(ord, ".,;:!?()[]{}'\"`·。，、：；！？（）【】「」"), None)
_LATEX_OP = re.compile(r"\\(?:times|cdot|times\{\}|mathrm\{x\})", re.IGNORECASE)
_MUL = str.maketrans({"×": "x", "✕": "x", "⋅": "x", "*": "x"})
_POINTS_RE = re.compile(r"POINTS\s+(\d+)\s*/\s*(\d+)")


def parse_points(text: str) -> tuple[int, int] | None:
    found = list(_POINTS_RE.finditer(text or ""))
    if not found:
        return None
    earned, total = found[-1].groups()
    return int(earned), int(total)


def _apply_points(grade: SampleGrade, pts: tuple[int, int] | None) -> SampleGrade:
    if pts is None and grade.passed is True:
        pts = (1, 1)
    if pts is None and grade.passed is False:
        pts = (0, 1)
    if pts is not None and pts[1] > 0:
        grade.points, grade.points_total = pts
        grade.score10 = round(10.0 * pts[0] / pts[1], 2)
    return grade

SANDBOX_BLOCK = """\
import socket
import subprocess

def _blocked(*_a, **_k):
    raise OSError("network disabled in model-lens sandbox")

socket.socket.connect = _blocked  # type: ignore[method-assign]
socket.create_connection = _blocked  # type: ignore[assignment]

def _no_sub(*_a, **_k):
    raise OSError("subprocess disabled in model-lens sandbox")

subprocess.Popen = _no_sub  # type: ignore[misc]
subprocess.run = _no_sub  # type: ignore[misc]
subprocess.call = _no_sub  # type: ignore[misc]
subprocess.check_call = _no_sub  # type: ignore[misc]
subprocess.check_output = _no_sub  # type: ignore[misc]
"""

_SANDBOX_KEEP = frozenset(
    {
        "PATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_MESSAGES",
        "TZ",
        "TMPDIR",
        "TMP",
        "TEMP",
    }
)


def grade_response(question: Question, content: str | None, *, repo_root: Path) -> SampleGrade:
    text = content if isinstance(content, str) else ""
    gtype = str(question.grader.get("type") or "")
    if gtype == "keyword":
        return _grade_keyword(question, text)
    if gtype == "alias":
        return _grade_alias(question, text)
    if gtype == "python_tests":
        return _grade_python(question, text, repo_root=repo_root)
    if gtype == "structure":
        return _grade_structure(question, text, repo_root=repo_root)
    return SampleGrade(
        temperature=0.0,
        status="error",
        passed=None,
        detail=f"unknown grader {gtype!r}",
        content=content,
    )


def extract_first_python_fence(text: str) -> str | None:
    if not text:
        return None
    labeled = _FENCE.search(text)
    if labeled:
        code = labeled.group(1).strip()
        return code or None
    unlabeled = _FENCE_ANY.search(text)
    if unlabeled:
        code = unlabeled.group(1).strip()
        if code and _looks_like_python(code):
            return code
    return None


def _looks_like_python(code: str) -> bool:
    return bool(re.search(r"^\s*(def|class|import|from)\b", code, re.MULTILINE))


def _norm(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text)
    folded = _LATEX_OP.sub("x", folded)
    folded = folded.translate(_MUL)
    return "".join(folded.translate(_PUNCT).casefold().split())


def _grade_keyword(question: Question, text: str) -> SampleGrade:
    groups = question.grader.get("must_include") or []
    min_hits = int(question.grader.get("min_hits") or 0)
    blob = _norm(text)
    hits = 0
    hit_labels: list[str] = []
    for group in groups:
        aliases = group if isinstance(group, list) else [group]
        if any(_norm(str(alias)) and _norm(str(alias)) in blob for alias in aliases):
            hits += 1
            hit_labels.append(str(aliases[0]))
    banned: list[str] = []
    for group in question.grader.get("must_exclude") or []:
        aliases = group if isinstance(group, list) else [group]
        if any(_norm(str(alias)) and _norm(str(alias)) in blob for alias in aliases):
            banned.append(str(aliases[0]))
    passed = hits >= min_hits and not banned
    n_groups = max(len(groups), 1)
    extra = f" banned={banned}" if banned else ""
    return _apply_points(
        SampleGrade(
            temperature=0.0,
            status="pass" if passed else "fail",
            passed=passed,
            detail=f"keyword hits={hits}/{min_hits} matched={hit_labels}{extra} POINTS {hits}/{n_groups}",
            content=text,
        ),
        (hits, n_groups),
    )


def _grade_alias(question: Question, text: str) -> SampleGrade:
    answers = question.grader.get("answers") or []
    match = str(question.grader.get("match") or "contains")
    blob = _norm(text)
    if not blob:
        return _apply_points(
            SampleGrade(
                temperature=0.0,
                status="fail",
                passed=False,
                detail="empty answer POINTS 0/1",
                content=text,
            ),
            (0, 1),
        )
    for alias in answers:
        key = _norm(str(alias))
        if not key:
            continue
        hit = blob == key if match == "exact" else key in blob
        if hit:
            return _apply_points(
                SampleGrade(
                    temperature=0.0,
                    status="pass",
                    passed=True,
                    detail=f"alias hit={alias} match={match} POINTS 1/1",
                    content=text,
                ),
                (1, 1),
            )
    return _apply_points(
        SampleGrade(
            temperature=0.0,
            status="fail",
            passed=False,
            detail="no alias matched POINTS 0/1",
            content=text,
        ),
        (0, 1),
    )


_FENCE_LANG = re.compile(
    r"```(?:json|text|txt|yaml|yml)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)


def extract_structure_payload(text: str) -> str | None:
    if not text or not text.strip():
        return None
    labeled = _FENCE_LANG.search(text)
    if labeled and labeled.group(1).strip():
        return labeled.group(1).rstrip("\n")
    unlabeled = _FENCE_ANY.search(text)
    if unlabeled and unlabeled.group(1).strip():
        return unlabeled.group(1).rstrip("\n")
    return text.strip() or None


def _grade_structure(question: Question, text: str, *, repo_root: Path) -> SampleGrade:
    payload = extract_structure_payload(text)
    if payload is None:
        return SampleGrade(
            temperature=0.0,
            status="missing",
            passed=None,
            detail="no structured payload",
            content=text,
        )
    rel = question.grader.get("tests_file")
    if not rel:
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail="grader.tests_file missing",
            content=text,
        )
    tests_path = repo_root / str(rel)
    if not tests_path.is_file():
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail=f"tests file not found: {rel}",
            content=text,
        )
    status, detail = run_sandbox("", tests_path, payload=payload)
    passed = status == "pass"
    return _apply_points(
        SampleGrade(
            temperature=0.0,
            status=status,
            passed=passed if status != "missing" else None,
            detail=detail,
            content=text,
        ),
        parse_points(detail),
    )


def _grade_python(question: Question, text: str, *, repo_root: Path) -> SampleGrade:
    code = extract_first_python_fence(text)
    if not code:
        return SampleGrade(
            temperature=0.0,
            status="missing",
            passed=None,
            detail="no fenced python block",
            content=text,
        )
    rel = question.grader.get("tests_file")
    if not rel:
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail="grader.tests_file missing",
            content=text,
        )
    tests_path = repo_root / str(rel)
    if not tests_path.is_file():
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail=f"tests file not found: {rel}",
            content=text,
        )
    status, detail = run_sandbox(code, tests_path)
    passed = status == "pass"
    return _apply_points(
        SampleGrade(
            temperature=0.0,
            status=status,
            passed=passed if status != "missing" else None,
            detail=detail,
            content=text,
        ),
        parse_points(detail),
    )


def run_sandbox(
    code: str,
    tests_path: Path,
    *,
    timeout_s: float = 8.0,
    payload: str | None = None,
) -> tuple[GradeStatus, str]:
    with tempfile.TemporaryDirectory(prefix="mlens-") as tmp:
        root = Path(tmp)
        (root / "sitecustomize.py").write_text(SANDBOX_BLOCK, encoding="utf-8")
        (root / "solution.py").write_text((code or "# payload-only") + "\n", encoding="utf-8")
        if payload is not None:
            (root / "payload.txt").write_text(payload, encoding="utf-8")
        (root / "test_q.py").write_text(tests_path.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "boot.py").write_text(
            "import sitecustomize\nimport runpy\nrunpy.run_path('test_q.py', run_name='__main__')\n",
            encoding="utf-8",
        )
        env = _sandbox_env(root)
        try:
            proc = subprocess.run(
                [sys.executable, "-s", str(root / "boot.py")],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return "fail", f"timeout>{timeout_s}s"
        blob = f"{proc.stdout or ''}\n{proc.stderr or ''}"
        pts = parse_points(blob)
        if pts is not None:
            earned, total = pts
            if earned == total and total > 0:
                return "pass", f"POINTS {earned}/{total}"
            extra = blob.strip()[-300:]
            return "fail", f"POINTS {earned}/{total}\n{extra}".strip()
        if proc.returncode == 0:
            return "pass", "sandbox ok"
        err = blob.strip()
        return "fail", err[-400:] or f"exit {proc.returncode}"


def _sandbox_env(tmp: Path) -> dict[str, str]:
    cleaned = {key: os.environ[key] for key in _SANDBOX_KEEP if key in os.environ}
    cleaned["PYTHONPATH"] = str(tmp)
    cleaned["PYTHONNOUSERSITE"] = "1"
    cleaned["NO_PROXY"] = "*"
    cleaned["no_proxy"] = "*"
    return cleaned


def attach_temperature(grade: SampleGrade, temperature: float) -> SampleGrade:
    grade.temperature = temperature
    return grade
