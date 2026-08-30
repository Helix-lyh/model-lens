"""把一场或多场 run 收成基层 gallery.json，并写出可切换模型的 HTML。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.bank import load_questions
from src.reasoning import extract_reasoning

SCHEMA = "model-lens.gallery.v1"
_TEMPLATE = Path(__file__).resolve().parent.parent / "web" / "gallery.html"


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
    questions = {q.id: q for q in load_questions(root)}
    models = [build_model(Path(run_dir), questions) for run_dir in run_dirs]
    return {"schema": SCHEMA, "models": models}


def build_model(run_dir: Path, questions: dict[str, Any]) -> dict[str, Any]:
    family_payload = _read_json(run_dir / "family.json") or _read_json(run_dir / "report.json") or {}
    bank = family_payload.get("bank") or _read_json(run_dir / "bank.json") or {}
    report = _read_json(run_dir / "report.json") or {}
    by_kind = _index_jsonl(run_dir / "requests.jsonl")
    claimed = family_payload.get("claimed") or report.get("claimed")
    target = family_payload.get("target") or report.get("target") or {}
    model_id = str((target or {}).get("model") or claimed or run_dir.name)
    rows = []
    for item in bank.get("questions") or []:
        qid = str(item.get("question_id") or "")
        spec = questions.get(qid)
        samples = []
        for i, sample in enumerate(item.get("samples") or []):
            kind = f"bank:{qid}:t{sample.get('temperature')}:n{i}"
            rec = by_kind.get(kind) or {}
            reasoning = sample.get("reasoning") or extract_reasoning(rec.get("raw"))
            if not reasoning:
                reasoning = rec.get("reasoning")
            samples.append(
                {
                    "temperature": sample.get("temperature"),
                    "status": sample.get("status"),
                    "passed": sample.get("passed"),
                    "detail": sample.get("detail"),
                    "answer": sample.get("content") if sample.get("content") is not None else rec.get("content"),
                    "reasoning": reasoning,
                    "latency_ms": rec.get("latency_ms"),
                    "points": sample.get("points"),
                    "points_total": sample.get("points_total"),
                    "score10": sample.get("score10"),
                }
            )
        rows.append(
            {
                "id": qid,
                "domain": item.get("domain") or (spec.domain if spec else None),
                "title": (spec.pass_criteria if spec else "") or qid,
                "prompt": spec.prompt if spec else "",
                "pass_criteria": spec.pass_criteria if spec else "",
                "expected": _expected(spec.grader) if spec else [],
                "pass0": item.get("pass0"),
                "majority": item.get("majority"),
                "score10": item.get("score10"),
                "difficulty": item.get("difficulty") or (spec.difficulty if spec else None),
                "samples": samples,
            }
        )
    columns = report.get("columns") or {}
    return {
        "id": model_id,
        "claimed": claimed,
        "run": run_dir.name,
        "target": {
            "base_url": (target or {}).get("base_url"),
            "model": (target or {}).get("model"),
            "channel": (target or {}).get("channel"),
        },
        "family": columns.get("family") or _family_brief(family_payload.get("family")),
        "identity": columns.get("identity") or family_payload.get("identity"),
        "degrade": columns.get("degrade") or family_payload.get("degrade"),
        "traffic": family_payload.get("traffic") or report.get("traffic"),
        "domains": (bank.get("domain_pass0") or {}),
        "domain_points": (bank.get("domain_points") or {}),
        "difficulty_points": (bank.get("difficulty_points") or {}),
        "quick": bool(bank.get("quick")),
        "n_questions": bank.get("n_questions") or len(bank.get("questions") or []),
        "questions": rows,
    }


def render_html(payload: dict[str, Any]) -> str:
    template = _TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False)
    return template.replace("/*__GALLERY_DATA__*/null", blob)


def _expected(grader: dict[str, Any] | None) -> list[str]:
    if not grader:
        return []
    if grader.get("type") == "alias":
        return [str(x) for x in (grader.get("answers") or [])]
    if grader.get("type") == "keyword":
        return [f"要点≥{grader.get('min_hits')}"]
    if grader.get("type") in {"python", "python_tests"}:
        return ["逐条计点，满点才通过"]
    if grader.get("type") == "structure":
        return ["结构断言逐条计点"]
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
