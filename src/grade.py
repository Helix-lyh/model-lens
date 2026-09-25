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

from src.fixtures import resolve_fixture_path
from src.toolchain import discover, ensure_cache_dirs
from src.types import GradeStatus, Question, SampleGrade

_FENCE_ANY = re.compile(r"```\s*\n(.*?)```", re.DOTALL)
_FENCE_TAGS = {
    "python": ("python", "py"),
    "go": ("go", "golang"),
    "typescript": ("typescript", "ts", "tsx", "javascript", "js"),
}
_GO_FORBIDDEN = re.compile(
    r'(?m)^\s*(?:import\s*)?(?:(?:\w+|\.|_)\s+)?(?:\(\s*)?"(net|net/http|os/exec|plugin)"'
)
_TS_MOD = r"(?:node:)?(?:fs(?:/promises)?|net|http|https|child_process|dgram)"
_TS_FORBIDDEN = re.compile(
    rf"""(?:from|import)\s+['"]{_TS_MOD}['"]"""
    rf"""|require\(\s*['"]{_TS_MOD}['"]\s*\)"""
    rf"""|import\(\s*['"]{_TS_MOD}['"]\s*\)"""
)
_LOOKS_LIKE = {
    "python": re.compile(r"^\s*(def|class|import|from)\b", re.MULTILINE),
    "go": re.compile(r"^\s*(package|func|type|import)\b", re.MULTILINE),
    "typescript": re.compile(r"^\s*(export|function|class|const|interface|type|import)\b", re.MULTILINE),
}
_PUNCT = dict.fromkeys(map(ord, ".,;:!?()[]{}'\"`·。，、：；！？（）【】「」"), None)
_LATEX_OP = re.compile(r"\\(?:times|cdot|times\{\}|mathrm\{x\})", re.IGNORECASE)
_MUL = str.maketrans({"×": "x", "✕": "x", "⋅": "x", "*": "x"})
_POINTS_LINE_RE = re.compile(r"^POINTS\s+([+-]?\d+)\s*/\s*([+-]?\d+)\s*$")


def _strip_source_comments(code: str) -> str:
    """Remove C-style comments before checking imports and dynamic loaders."""
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.DOTALL)


def parse_points(text: str) -> tuple[int, int] | None:
    """只认 stdout 最后一条 POINTS 行；非法最终 marker 不回退到更早结果。"""
    markers = [line.strip() for line in (text or "").splitlines() if line.strip().startswith("POINTS")]
    if not markers:
        return None
    found = _POINTS_LINE_RE.fullmatch(markers[-1])
    if found is None:
        return None
    earned, total = (int(value) for value in found.groups())
    if total <= 0 or earned < 0 or earned > total:
        return None
    return earned, total


def _apply_points(grade: SampleGrade, pts: tuple[int, int] | None) -> SampleGrade:
    if pts is None and grade.passed is False:
        pts = (0, 1)
    if pts is not None:
        earned, total = pts
        if total > 0 and 0 <= earned <= total:
            grade.points, grade.points_total = earned, total
            grade.score10 = round(10.0 * earned / total, 2)
    return grade

SANDBOX_BLOCK = """\
import builtins
import os
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

def _no_process(*_a, **_k):
    raise OSError("process execution disabled in model-lens sandbox")

os.system = _no_process
os.popen = _no_process
for _name in ("spawnv", "spawnve", "spawnl", "spawnle", "spawnlp", "spawnlpe"):
    if hasattr(os, _name):
        setattr(os, _name, _no_process)

_real_import = builtins.__import__
def _safe_import(name, *args, **kwargs):
    if name == "ctypes" or name.startswith("ctypes."):
        raise ImportError("ctypes disabled in model-lens sandbox")
    return _real_import(name, *args, **kwargs)
builtins.__import__ = _safe_import
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
    if gtype == "code_tests":
        return _grade_code(question, text, repo_root=repo_root)
    if gtype == "structure":
        return _grade_structure(question, text, repo_root=repo_root)
    return SampleGrade(
        temperature=0.0,
        status="error",
        passed=None,
        detail=f"unknown grader {gtype!r}",
        content=content,
    )


def extract_fenced_code(text: str, language: str) -> str | None:
    if not text:
        return None
    tags = _FENCE_TAGS.get(language, (language,))
    alt = "|".join(re.escape(tag) for tag in tags)
    labeled = re.search(rf"```(?:{alt})\s*\n(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if labeled:
        code = labeled.group(1).strip()
        return code or None
    unlabeled = _FENCE_ANY.search(text)
    if unlabeled:
        code = unlabeled.group(1).strip()
        looks = _LOOKS_LIKE.get(language)
        if code and looks is not None and looks.search(code):
            return code
    return None


def _norm(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text)
    folded = _LATEX_OP.sub("x", folded)
    folded = folded.translate(_MUL)
    return "".join(folded.translate(_PUNCT).casefold().split())


def _hits_in_groups(groups: Any, blob: str) -> list[str]:
    labels: list[str] = []
    for group in groups or []:
        aliases = group if isinstance(group, list) else [group]
        if any(_norm(str(alias)) and _norm(str(alias)) in blob for alias in aliases):
            labels.append(str(aliases[0]))
    return labels


def _grade_keyword(question: Question, text: str) -> SampleGrade:
    groups = question.grader.get("must_include") or []
    min_hits = int(question.grader.get("min_hits") or 0)
    blob = _norm(text)
    hit_labels = _hits_in_groups(groups, blob)
    hits = len(hit_labels)
    banned = _hits_in_groups(question.grader.get("must_exclude") or [], blob)
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
    # Strict protocol questions must be judged against the response bytes as returned:
    # do not silently remove Markdown fences, surrounding whitespace, or explanations.
    payload = text if question.grader.get("strict_response") else extract_structure_payload(text)
    if payload is None or (question.grader.get("strict_response") and not str(payload).strip()):
        # HTTP 200 空正文是答错，不是缺测。missing 只留给传输失败 / 无工具链。
        return _apply_points(
            SampleGrade(
                temperature=0.0,
                status="fail",
                passed=False,
                detail="no structured payload POINTS 0/1",
                content=text,
            ),
            (0, 1),
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
    try:
        tests_path = resolve_fixture_path(repo_root, rel, question_id=question.id)
    except ValueError as exc:
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail=str(exc),
            content=text,
        )
    status, detail = run_python_sandbox(
        "", tests_path, payload=payload,
        result_marker=str(question.grader.get("result_marker") or "") or None,
    )
    passed = status == "pass"
    return _apply_points(
        SampleGrade(
            temperature=0.0,
            status=status,
            passed=passed if status != "missing" else None,
            detail=detail,
            content=text,
        ),
        _trusted_points(detail) if "result_marker" in question.grader else parse_points(detail),
    )


def _code_from_answer(question: Question, text: str) -> SampleGrade | tuple[str, str]:
    lang = question.language
    if not lang:
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail="question.language missing",
            content=text,
        )
    code = extract_fenced_code(text, lang)
    if not code:
        return SampleGrade(
            temperature=0.0,
            status="missing",
            passed=None,
            detail=f"no fenced {lang} block",
            content=text,
        )
    return lang, code


def _resolve_tests_file(question: Question, text: str, repo_root: Path) -> SampleGrade | Path:
    rel = question.grader.get("tests_file")
    if not rel:
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail="grader.tests_file missing",
            content=text,
        )
    try:
        return resolve_fixture_path(repo_root, rel, question_id=question.id)
    except ValueError as exc:
        return SampleGrade(
            temperature=0.0,
            status="error",
            passed=None,
            detail=str(exc),
            content=text,
        )


def _toolchain_gap(lang: str, text: str) -> SampleGrade | None:
    missing = discover().missing_for(lang)
    if not missing:
        return None
    return SampleGrade(
        temperature=0.0,
        status="missing",
        passed=None,
        detail=f"toolchain missing: {', '.join(missing)}",
        content=text,
    )


def _forbidden_grade(code: str, lang: str, text: str) -> SampleGrade | None:
    banned = _forbidden_import(code, lang)
    if not banned:
        return None
    return _apply_points(
        SampleGrade(
            temperature=0.0,
            status="fail",
            passed=False,
            detail=f"forbidden import {banned} POINTS 0/1",
            content=text,
        ),
        (0, 1),
    )


def _run_lang_sandbox(
    lang: str, code: str, tests_path: Path, *, result_marker: str | None = None
) -> tuple[GradeStatus, str]:
    if lang == "python":
        return run_python_sandbox(code, tests_path, result_marker=result_marker)
    if lang == "go":
        return run_go_sandbox(code, tests_path, result_marker=result_marker)
    if lang == "typescript":
        return run_ts_sandbox(code, tests_path, result_marker=result_marker)
    return "error", f"unsupported language {lang!r}"


def _trusted_points(detail: str) -> tuple[int, int] | None:
    if not detail.startswith("FIXTURE_RESULT\n"):
        return None
    return parse_points(detail)


def _code_sample_grade(status: GradeStatus, detail: str, text: str) -> SampleGrade:
    if status in {"missing", "error"}:
        return SampleGrade(
            temperature=0.0,
            status=status,
            passed=None,
            detail=detail,
            content=text,
        )
    # Only a result explicitly extracted from the fixture may contribute
    # points. Candidate stdout is diagnostic text and is never score input.
    pts = _trusted_points(detail)
    if pts is None and not detail.startswith("FIXTURE_RESULT\n"):
        # Direct sandbox callers retain the historical fixture contract; the
        # production coding runners always set result_marker above.
        pts = parse_points(detail)
    if pts is None and status == "fail":
        pts = (0, 1)
    return _apply_points(
        SampleGrade(
            temperature=0.0,
            status=status,
            passed=status == "pass",
            detail=detail,
            content=text,
        ),
        pts,
    )


def _grade_code(question: Question, text: str, *, repo_root: Path) -> SampleGrade:
    pulled = _code_from_answer(question, text)
    if isinstance(pulled, SampleGrade):
        return pulled
    lang, code = pulled
    tests = _resolve_tests_file(question, text, repo_root)
    if isinstance(tests, SampleGrade):
        return tests
    gap = _toolchain_gap(lang, text)
    if gap is not None:
        return gap
    banned = _forbidden_grade(code, lang, text)
    if banned is not None:
        return banned
    status, detail = _run_lang_sandbox(
        lang, code, tests,
        result_marker=str(question.grader.get("result_marker") or "") or None,
    )
    return _code_sample_grade(status, detail, text)


def _forbidden_import(code: str, lang: str) -> str | None:
    if lang == "go":
        hit = _GO_FORBIDDEN.search(_strip_source_comments(code))
        return hit.group(1) if hit else None
    if lang == "typescript":
        clean = _strip_source_comments(code)
        hit = _TS_FORBIDDEN.search(clean)
        if hit:
            return hit.group(0)
        dynamic = re.search(
            r"(?:eval\s*\(|Function\s*\(|(?:globalThis\.)?require\s*\(|"
            r"process\s*\.\s*(?:binding|getBuiltinModule)\s*\()",
            clean,
        )
        return dynamic.group(0) if dynamic else None
    return None


def run_python_sandbox(
    code: str,
    tests_path: Path,
    *,
    timeout_s: float = 8.0,
    payload: str | None = None,
    result_marker: str | None = None,
) -> tuple[GradeStatus, str]:
    with tempfile.TemporaryDirectory(prefix="mlens-") as tmp:
        root = Path(tmp)
        (root / "sitecustomize.py").write_text(SANDBOX_BLOCK, encoding="utf-8")
        (root / "solution.py").write_text((code or "# payload-only") + "\n", encoding="utf-8")
        if payload is not None:
            (root / "payload.txt").write_text(payload, encoding="utf-8")
        helper = tests_path.parent / "_structured.py"
        if helper.is_file():
            (root / "_structured.py").write_text(helper.read_text(encoding="utf-8"), encoding="utf-8")
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
        return _sandbox_result(proc, result_marker=result_marker)


def run_go_sandbox(
    code: str, tests_path: Path, *, timeout_s: float = 15.0,
    result_marker: str | None = None,
) -> tuple[GradeStatus, str]:
    tools = discover()
    if tools.missing_for("go"):
        return "missing", f"toolchain missing: {', '.join(tools.missing_for('go'))}"
    go = tools.go.path
    assert go
    cache = ensure_cache_dirs()
    with tempfile.TemporaryDirectory(prefix="mlens-go-") as tmp:
        root = Path(tmp)
        (root / "go.mod").write_text("module solution\n\ngo 1.20\n", encoding="utf-8")
        (root / "solution.go").write_text(code.rstrip() + "\n", encoding="utf-8")
        dest = root / tests_path.name
        if not dest.name.endswith("_test.go"):
            dest = root / "solution_test.go"
        dest.write_text(tests_path.read_text(encoding="utf-8"), encoding="utf-8")
        env = _sandbox_env(root)
        env["PATH"] = str(Path(go).parent) + os.pathsep + env.get("PATH", "")
        env["GOPROXY"] = "off"
        env["GOSUMDB"] = "off"
        env["GOTOOLCHAIN"] = "local"
        env["GOCACHE"] = str(cache / "gocache")
        env["GOMODCACHE"] = str(root / ".gomodcache")
        env["GOFLAGS"] = "-mod=mod"
        env["CGO_ENABLED"] = "0"
        try:
            proc = subprocess.run(
                [go, "test", "-count=1", "-v", "."],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return "fail", f"timeout>{timeout_s}s"
        return _sandbox_result(proc, result_marker=result_marker)


_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "strict": false,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": ".",
    "noEmitOnError": true
  },
  "include": ["*.ts"]
}
"""


def run_ts_sandbox(
    code: str, tests_path: Path, *, timeout_s: float = 45.0,
    result_marker: str | None = None,
) -> tuple[GradeStatus, str]:
    tools = discover()
    missing = tools.missing_for("typescript")
    if missing:
        return "missing", f"toolchain missing: {', '.join(missing)}"
    tsc = list(tools.tsc.argv)
    node = tools.node.path
    assert tsc and node
    with tempfile.TemporaryDirectory(prefix="mlens-ts-") as tmp:
        root = Path(tmp)
        (root / "tsconfig.json").write_text(_TSCONFIG, encoding="utf-8")
        (root / "solution.ts").write_text(code.rstrip() + "\n", encoding="utf-8")
        (root / "run_test.ts").write_text(tests_path.read_text(encoding="utf-8"), encoding="utf-8")
        compile_env = _toolchain_env(root)
        compile_env["PATH"] = str(Path(node).parent) + os.pathsep + compile_env.get("PATH", "")
        try:
            compiled = subprocess.run(
                [*tsc, "-p", "tsconfig.json", "--pretty", "false"],
                cwd=root,
                env=compile_env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return "fail", f"timeout>{timeout_s}s"
        if compiled.returncode != 0:
            blob = f"{compiled.stdout or ''}\n{compiled.stderr or ''}".strip()
            return "fail", f"compile failed\n{blob[-400:]}" if blob else "compile failed"
        js = root / "dist" / "run_test.js"
        if not js.is_file():
            return "fail", "compile produced no run_test.js"
        run_env = _sandbox_env(root)
        run_env["PATH"] = str(Path(node).parent) + os.pathsep + run_env.get("PATH", "")
        try:
            proc = subprocess.run(
                [node, str(js)],
                cwd=root / "dist",
                env=run_env,
                capture_output=True,
                text=True,
                timeout=min(timeout_s, 8.0),
            )
        except subprocess.TimeoutExpired:
            return "fail", f"timeout>{min(timeout_s, 8.0)}s"
        return _sandbox_result(proc, result_marker=result_marker)


def _sandbox_result(
    proc: subprocess.CompletedProcess[str], *, result_marker: str | None = None
) -> tuple[GradeStatus, str]:
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    # A process that exited abnormally can never pass, even if it printed a marker.
    if proc.returncode != 0:
        diagnostic = stdout.strip() or stderr.strip()
        return "fail", diagnostic[-400:] or f"exit {proc.returncode}"
    if result_marker:
        lines = []
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if line.startswith(result_marker):
                lines.append(line[len(result_marker):].lstrip())
        pts = parse_points("\n".join(lines))
        if pts is None:
            if any(line.startswith("CASE ") for line in lines):
                return "pass", "FIXTURE_RESULT\n" + "\n".join(lines)
            diagnostic = stdout.strip() or stderr.strip()
            return "fail", diagnostic[-400:] or "no fixture result"
        detail = "FIXTURE_RESULT\n" + "\n".join(lines)
        earned, total = pts
        return ("pass" if earned == total else "fail"), detail
    pts = parse_points(stdout)
    if pts is not None:
        earned, total = pts
        if earned == total:
            return "pass", f"POINTS {earned}/{total}"
        diagnostic = stdout.strip()
        return "fail", f"POINTS {earned}/{total}\n{diagnostic[-300:]}".strip()
    diagnostic = stdout.strip() or stderr.strip()
    return "fail", diagnostic[-400:] or "no POINTS in sandbox output"


def _sandbox_env(tmp: Path) -> dict[str, str]:
    cleaned = {key: os.environ[key] for key in _SANDBOX_KEEP if key in os.environ}
    cleaned["PYTHONPATH"] = str(tmp)
    cleaned["PYTHONNOUSERSITE"] = "1"
    cleaned["NO_PROXY"] = "*"
    cleaned["no_proxy"] = "*"
    return cleaned


def _toolchain_env(tmp: Path) -> dict[str, str]:
    cleaned = _sandbox_env(tmp)
    for key in ("HOME", "NPM_CONFIG_CACHE", "npm_config_cache", "XDG_CACHE_HOME"):
        if key in os.environ:
            cleaned[key] = os.environ[key]
    return cleaned


def attach_temperature(grade: SampleGrade, temperature: float) -> SampleGrade:
    grade.temperature = temperature
    return grade
