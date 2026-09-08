"""把一场或多场 run 收成基层 gallery.json，并写出可切换模型的 HTML。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.bank import load_questions
from src.cluster import cluster_id_from_row, language_of, raw_matrix_from_bank
from src.reasoning import extract_reasoning

SCHEMA = "model-lens.gallery.v1"
_TEMPLATE = Path(__file__).resolve().parent.parent / "web" / "gallery.html"
_CODE_TYPES = frozenset({"code_tests"})
_CRITERIA_TYPES = frozenset({"alias", "keyword", "structure"})


def write_run_gallery(run_dir: Path, *, root: Path | None = None) -> dict[str, Any]:
    payload = build_gallery([run_dir], root=root)
    run_dir = Path(run_dir)
    (run_dir / "gallery.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def write_gallery(run_dirs: list[Path], out_dir: Path, *, root: Path | None = None) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_gallery(run_dirs, root=root)
    data_path = out_dir / "gallery.json"
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html = render_html(payload)
    html_path = out_dir / "gallery.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def build_gallery(run_dirs: list[Path], *, root: Path | None = None) -> dict[str, Any]:
    need_bank = any(_run_has_bank_questions(Path(run_dir)) for run_dir in run_dirs)
    questions = {q.id: q for q in load_questions(root)} if need_bank else {}
    models = [build_model(Path(run_dir), questions) for run_dir in run_dirs]
    return {"schema": SCHEMA, "models": models}


def _run_has_bank_questions(run_dir: Path) -> bool:
    src = _read_json(run_dir / "report.json") or _read_json(run_dir / "family.json") or {}
    bank = src.get("bank") or _read_json(run_dir / "bank.json") or {}
    return bool(isinstance(bank, dict) and bank.get("questions"))


def build_model(run_dir: Path, questions: dict[str, Any]) -> dict[str, Any]:
    src = _read_json(run_dir / "report.json") or _read_json(run_dir / "family.json") or {}
    bank = src.get("bank") or _read_json(run_dir / "bank.json") or {}
    by_kind = _index_jsonl(run_dir / "requests.jsonl")
    claimed = src.get("claimed")
    target = src.get("target") or {}
    columns = _columns(src)
    return {
        "id": str(target.get("model") or claimed or run_dir.name),
        "claimed": claimed,
        "run": run_dir.name,
        "target": {
            "base_url": target.get("base_url"),
            "model": target.get("model"),
            "channel": target.get("channel"),
        },
        "family": columns["family"],
        "identity": columns["identity"],
        "degrade": columns["degrade"],
        "traffic": src.get("traffic"),
        "domains": bank.get("domain_pass0") or {},
        "domain_points": bank.get("domain_points") or {},
        "difficulty_points": bank.get("difficulty_points") or {},
        "quick": bool(bank.get("quick")),
        "schema_version": bank.get("schema_version") or "model-lens.bank.v1",
        "bank_version": bank.get("bank_version"),
        "scorer_version": bank.get("scorer_version"),
        "sampling_protocol": bank.get("sampling_protocol"),
        "raw_question_count": bank.get("raw_question_count") or _raw_count(bank),
        "expanded_question_count": bank.get("expanded_question_count") or bank.get("n_questions") or len(bank.get("questions") or []),
        "raw_domain_counts": bank.get("raw_domain_counts") or {},
        "raw_difficulty_counts": bank.get("raw_difficulty_counts") or {},
        "expanded_domain_counts": bank.get("expanded_domain_counts") or {},
        "expanded_difficulty_counts": bank.get("expanded_difficulty_counts") or {},
        "coding_cluster_count": bank.get("coding_cluster_count") or _coding_count(bank),
        "coding_variant_count": bank.get("coding_variant_count") or _coding_variant_count(bank),
        "coding_available": bank.get("coding_available") or {},
        "coding_strict": bank.get("coding_strict") or {},
        "raw_matrix": bank.get("raw_matrix") or _raw_matrix(bank),
        "coding_cluster_diagnostics": bank.get("coding_cluster_diagnostics") or {},
        "n_questions": bank.get("n_questions") or len(bank.get("questions") or []),
        "questions": [
            _question_row(item, questions.get(str(item.get("question_id") or "")), by_kind)
            for item in bank.get("questions") or []
        ],
    }


def render_html(payload: dict[str, Any]) -> str:
    template = _TEMPLATE.read_text(encoding="utf-8")
    # HTML's script-data parser recognizes </script> even in JSON strings.
    blob = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    return template.replace("/*__GALLERY_DATA__*/null", blob)


def _row_language(row: dict[str, Any]) -> str | None:
    language = row.get("language")
    lang = language if isinstance(language, str) else None
    return language_of(lang, str(row.get("question_id") or ""))


def _row_cluster_id(row: dict[str, Any]) -> str | None:
    return cluster_id_from_row(row)


def _raw_count(bank: dict[str, Any]) -> int:
    keys = {
        key
        for row in bank.get("questions") or []
        if isinstance(row, dict)
        for key in [_row_cluster_id(row)]
        if key
    }
    return len(keys)


def _coding_count(bank: dict[str, Any]) -> int:
    keys = {
        key
        for row in bank.get("questions") or []
        if isinstance(row, dict) and row.get("domain") == "coding"
        for key in [_row_cluster_id(row)]
        if key
    }
    return len(keys)


def _coding_variant_count(bank: dict[str, Any]) -> int:
    return sum(
        1
        for row in bank.get("questions") or []
        if isinstance(row, dict) and row.get("domain") == "coding" and _row_language(row)
    )


def _raw_matrix(bank: dict[str, Any]) -> dict[str, dict[str, int]]:
    return raw_matrix_from_bank(bank)


def _columns(src: dict[str, Any]) -> dict[str, Any]:
    cols = src.get("columns")
    if isinstance(cols, dict):
        return {
            "family": cols.get("family"),
            "identity": cols.get("identity"),
            "degrade": cols.get("degrade"),
        }
    return {
        "family": _family_brief(src.get("family")),
        "identity": src.get("identity"),
        "degrade": src.get("degrade"),
    }


def _question_row(item: dict[str, Any], spec: Any, by_kind: dict[str, dict[str, Any]]) -> dict[str, Any]:
    qid = str(item.get("question_id") or "")
    return {
        "id": qid,
        "domain": item.get("domain") or (spec.domain if spec else None),
        "title": (spec.pass_criteria if spec else "") or qid,
        "prompt": spec.prompt if spec else "",
        "pass_criteria": spec.pass_criteria if spec else "",
        "expected": _expected(spec.grader, spec.language if spec else None) if spec else [],
        "pass0": item.get("pass0"),
        "majority": item.get("majority"),
        "score10": item.get("score10"),
        "difficulty": item.get("difficulty") or (spec.difficulty if spec else None),
        "raw_id": item.get("raw_id") or (spec.raw_id if spec else None),
        "cluster_id": item.get("cluster_id") or (spec.cluster_id if spec else None),
        "language": spec.language if spec else item.get("language"),
        "construct": item.get("construct") or (spec.construct if spec else None),
        "question_hash": item.get("question_hash"),
        "fixture_hash": item.get("fixture_hash"),
        "samples": _samples_for(item, qid, by_kind),
    }


def _samples_for(item: dict[str, Any], qid: str, by_kind: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for i, sample in enumerate(item.get("samples") or []):
        rec = by_kind.get(f"bank:{qid}:t{sample.get('temperature')}:n{i}") or {}
        rows.append(
            {
                "temperature": sample.get("temperature"),
                "status": sample.get("status"),
                "passed": sample.get("passed"),
                "detail": sample.get("detail"),
                "answer": sample.get("content") if sample.get("content") is not None else rec.get("content"),
                "reasoning": sample.get("reasoning") or extract_reasoning(rec.get("raw")) or rec.get("reasoning"),
                "latency_ms": rec.get("latency_ms"),
                "points": sample.get("points"),
                "points_total": sample.get("points_total"),
                "score10": sample.get("score10"),
            }
        )
    return rows


def _expected(grader: dict[str, Any] | None, language: str | None = None) -> list[str]:
    if not grader:
        return []
    gtype = grader.get("type")
    if gtype in _CODE_TYPES:
        lang = language or grader.get("language")
        return [f"{lang} 逐条计点"] if lang else ["逐条计点"]
    if gtype in _CRITERIA_TYPES:
        return ["见 pass_criteria"]
    return []


def _family_brief(fam: Any) -> dict[str, Any] | None:
    if not isinstance(fam, dict):
        return None
    return {
        "status": fam.get("status"),
        "family": fam.get("family"),
        "hits": fam.get("hits"),
        "n_probes": fam.get("n_probes"),
        "l1": fam.get("l1"),
        "confidence": fam.get("confidence"),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _index_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if isinstance(rec, dict) and rec.get("kind"):
            out[str(rec["kind"])] = rec
    return out
