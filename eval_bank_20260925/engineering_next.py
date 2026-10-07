"""Executable scorers for the 20261008 engineering items E-07..E-10.

The fixture observes only the public event contract.  Each relation is either
an equality with a literal or a required distinction/equality between two
observations.  Codes are deliberately opaque to the prompt.
"""
from __future__ import annotations

import inspect
import json
import tempfile
from pathlib import Path

from src.grade import grade_response
from src.types import Question

LEDGER = 20


def _e(op: str, **fields):
    # The prompt names event variants (BATCH/SHIP/...), while answers commonly
    # encode that variant as either `op` or `type`; expose both spellings in
    # the fixture so the scorer tests the business state machine rather than a
    # hidden transport-key convention.
    return {"op": op, "type": op, **fields}


def _pack(code: str, **extra):
    row = {"code": code, "reason": code}
    row.update(extra)
    return row


CASES = {
    "E-07": {
        "registered": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("READ", batch="b")],
        "ship": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("SHIP", batch="b", order="o", qty=3, request_id="r", temp=5)],
        "retry": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("SHIP", batch="b", order="o", qty=3, request_id="r", temp=5), _e("SHIP", batch="b", order="o", qty=3, request_id="r", temp=5)],
        "badtemp": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("SHIP", batch="b", order="o", qty=1, request_id="x", temp=9)],
        "lowtemp": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("SHIP", batch="b", order="o", qty=1, request_id="x", temp=1)],
        "defaulttemp": [_e("BATCH", batch="b", temp_min=2, temp_max=8, temp=5), _e("SHIP", batch="b", order="o", qty=1, request_id="x")],
        "hold": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("HOLD", batch="b", request_id="h"), _e("SHIP", batch="b", order="o", qty=1, request_id="x", temp=5)],
        "holdread": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("HOLD", batch="b", request_id="h"), _e("READ", batch="b")],
        "unknown": [_e("READ", batch="missing")],
        "short": [_e("BATCH", batch="b", temp_min=2, temp_max=8, qty=2), _e("SHIP", batch="b", order="o", qty=3, request_id="x", temp=5), _e("READ", batch="b")],
        "change": [_e("BATCH", batch="b", temp_min=2, temp_max=8, temp=5), _e("BATCH", batch="b", temp_min=2, temp_max=8, temp=9), _e("SHIP", batch="b", order="o", qty=1, request_id="x")],
        "other": [_e("BATCH", batch="a", temp_min=2, temp_max=8, qty=2), _e("BATCH", batch="b", temp_min=2, temp_max=8, qty=4), _e("SHIP", batch="a", order="o", qty=1, request_id="a", temp=5), _e("READ", batch="b")],
        "negative": [_e("BATCH", batch="b", temp_min=2, temp_max=8, qty=2), _e("SHIP", batch="b", order="o", qty=-1, request_id="x", temp=5), _e("READ", batch="b")],
        "dup_batch": [_e("BATCH", batch="b", temp_min=2, temp_max=8, qty=2), _e("BATCH", batch="b", temp_min=2, temp_max=8, qty=9), _e("READ", batch="b")],
        "order_distinct": [_e("BATCH", batch="b", temp_min=2, temp_max=8, qty=5), _e("SHIP", batch="b", order="a", qty=1, request_id="a", temp=5), _e("SHIP", batch="b", order="b", qty=1, request_id="b", temp=5), _e("READ", batch="b")],
        "hold_retry": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("HOLD", batch="b", request_id="h"), _e("HOLD", batch="b", request_id="h")],
        "hold_other": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("HOLD", batch="b", request_id="h"), _e("HOLD", batch="b", request_id="x")],
        "zero": [_e("BATCH", batch="b", temp_min=2, temp_max=8, qty=0), _e("READ", batch="b")],
        "order_retry_diff": [_e("BATCH", batch="b", temp_min=2, temp_max=8), _e("SHIP", batch="b", order="o", qty=1, request_id="r", temp=5), _e("SHIP", batch="b", order="o", qty=2, request_id="s", temp=5)],
    },
    "E-08": {
        "case": [_e("CASE", case="c", order="o", deadline=10), _e("READ", case="c")],
        "evidence": [_e("CASE", case="c", order="o", deadline=10), _e("EVIDENCE", case="c", evidence_id="e", kind="receipt", at=5, request_id="r"), _e("READ", case="c")],
        "dup": [_e("CASE", case="c", order="o", deadline=10), _e("EVIDENCE", case="c", evidence_id="e", kind="receipt", at=5, request_id="r"), _e("EVIDENCE", case="c", evidence_id="e", kind="receipt", at=5, request_id="r2"), _e("READ", case="c")],
        "late": [_e("CASE", case="c", order="o", deadline=10), _e("EVIDENCE", case="c", evidence_id="e", kind="receipt", at=10, request_id="r"), _e("READ", case="c")],
        "submit": [_e("CASE", case="c", order="o", deadline=10), _e("EVIDENCE", case="c", evidence_id="e", kind="receipt", at=5, request_id="r"), _e("SUBMIT", case="c", at=10, request_id="s"), _e("READ", case="c")],
        "submitlate": [_e("CASE", case="c", order="o", deadline=10), _e("SUBMIT", case="c", at=11, request_id="s")],
        "after": [_e("CASE", case="c", order="o", deadline=10), _e("SUBMIT", case="c", at=10, request_id="s"), _e("EVIDENCE", case="c", evidence_id="e", at=5, request_id="r"), _e("READ", case="c")],
        "retry": [_e("CASE", case="c", order="o", deadline=10), _e("SUBMIT", case="c", at=10, request_id="s"), _e("SUBMIT", case="c", at=10, request_id="s"), _e("READ", case="c")],
        "unknown": [_e("READ", case="z")],
        "other": [_e("CASE", case="a", order="o", deadline=10), _e("CASE", case="b", order="o", deadline=10), _e("EVIDENCE", case="a", evidence_id="e", at=5, request_id="a"), _e("READ", case="b")],
        "kind": [_e("CASE", case="c", order="o", deadline=10), _e("EVIDENCE", case="c", evidence_id="e", kind="photo", at=5, request_id="r")],
        "missingkind": [_e("CASE", case="c", order="o", deadline=10), _e("EVIDENCE", case="c", evidence_id="e", at=5, request_id="r")],
    },
    "E-09": {
        "claim": [_e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=0), _e("READ", device="d", at=0)],
        "renew": [_e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=0), _e("RENEW", device="d", worker="w", ttl=20, request_id="n", at=5)],
        "old": [_e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=0), _e("RENEW", device="d", worker="x", ttl=20, request_id="n", at=5)],
        "expire": [_e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=0), _e("READ", device="d", at=10)],
        "boundary": [_e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=0), _e("READ", device="d", at=9)],
        "maintain": [_e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=0), _e("MAINTAIN", device="d", enabled=True, request_id="m", at=1), _e("READ", device="d", at=1)],
        "maintain_claim": [_e("MAINTAIN", device="d", enabled=True, request_id="m", at=1), _e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=1)],
        "close": [_e("MAINTAIN", device="d", enabled=True, request_id="m", at=1), _e("MAINTAIN", device="d", enabled=False, request_id="n", at=2), _e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=2)],
        "retry": [_e("CLAIM", device="d", worker="w", ttl=10, request_id="r", at=0), _e("CLAIM", device="d", worker="x", ttl=5, request_id="r", at=1)],
        "other": [_e("CLAIM", device="a", worker="w", ttl=10, request_id="a", at=0), _e("READ", device="b", at=0)],
        "maintain_retry": [_e("MAINTAIN", device="d", enabled=True, request_id="m", at=1), _e("MAINTAIN", device="d", enabled=True, request_id="m", at=2)],
    },
    "E-10": {
        "rate": [_e("RATE", region="r", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="d"), _e("ISSUE", invoice="i", request_id="s")],
        "items": [_e("RATE", region="r", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="a"), _e("DRAFT", invoice="i", item="b", region="r", net=50, request_id="b"), _e("ISSUE", invoice="i", request_id="s")],
        "round": [_e("RATE", region="r", version=1, bps=3333), _e("DRAFT", invoice="i", item="a", region="r", net=10, request_id="a"), _e("ISSUE", invoice="i", request_id="s")],
        "freeze": [_e("RATE", region="r", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="a"), _e("ISSUE", invoice="i", request_id="s"), _e("RATE", region="r", version=2, bps=2000), _e("READ", invoice="i")],
        "default": [_e("RATE", region="default", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", net=100, request_id="a"), _e("ISSUE", invoice="i", request_id="s")],
        "dupitem": [_e("RATE", region="r", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="a"), _e("DRAFT", invoice="i", item="a", region="r", net=200, request_id="b"), _e("ISSUE", invoice="i", request_id="s")],
        "void": [_e("RATE", region="r", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="a"), _e("ISSUE", invoice="i", request_id="s"), _e("VOID", invoice="i", request_id="v"), _e("READ", invoice="i")],
        "void_issue": [_e("RATE", region="r", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="a"), _e("VOID", invoice="i", request_id="v"), _e("ISSUE", invoice="i", request_id="s")],
        "retry": [_e("RATE", region="r", version=1, bps=1000), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="a"), _e("DRAFT", invoice="i", item="a", region="r", net=100, request_id="a")],
        "unknown": [_e("READ", invoice="z")],
        "regions": [_e("RATE", region="a", version=1, bps=1000), _e("RATE", region="b", version=1, bps=2000), _e("DRAFT", invoice="i", item="x", region="a", net=100, request_id="a"), _e("DRAFT", invoice="j", item="x", region="b", net=100, request_id="b"), _e("ISSUE", invoice="i", request_id="s"), _e("ISSUE", invoice="j", request_id="t")],
    },
}


def _make_pairs(item_id: str):
    # All entries are observable.  Literal checks carry payload obligations;
    # distinction checks exercise the code/reason relation contract.
    if item_id == "E-07":
        return [
            ["registered", ["registered", 1, "code"], ["registered", 0, "code"], False, "eq"],
            ["ship_code", ["ship", 1, "code"], ["badtemp", 1, "code"], False, "eq"],
            ["retry_same", ["retry", 1, "code"], ["retry", 2, "code"], True, "eq"],
            ["retry_available", ["retry", 2, "available"], ["ship", 1, "available"], True, "eq"],
            ["high_temp", ["badtemp", 1, "code"], ["lowtemp", 1, "code"], True, "eq"],
            ["default_temp", ["defaulttemp", 1, "code"], ["ship", 1, "code"], True, "eq"],
            ["hold_code", ["hold", 2, "code"], ["badtemp", 1, "code"], False, "eq"],
            ["hold_read", ["holdread", 2, "code"], ["hold", 1, "code"], True, "eq"],
            ["unknown", ["unknown", 0, "code"], ["badtemp", 1, "code"], False, "eq"],
            ["short_available", ["short", 2, "available"], ["zero", 1, "available"], False, "eq"],
            ["change_temp", ["change", 2, "code"], ["badtemp", 1, "code"], True, "eq"],
            ["cross_batch", ["other", 3, "available"], ["ship", 1, "available"], False, "eq"],
            ["negative", ["negative", 1, "code"], ["short", 1, "code"], True, "eq"],
            ["dup_batch_read", ["dup_batch", 2, "available"], ["zero", 1, "available"], False, "eq"],
            ["order_count", ["order_distinct", 3, "available"], ["ship", 1, "available"], False, "eq"],
            ["hold_retry", ["hold_retry", 2, "code"], ["hold", 1, "code"], True, "eq"],
            ["hold_other", ["hold_other", 2, "code"], ["hold", 1, "code"], True, "eq"],
            ["zero_batch", ["zero", 1, "available"], ["registered", 1, "available"], False, "eq"],
            ["order_retry_diff", ["order_retry_diff", 2, "code"], ["ship", 1, "code"], True, "eq"],
            ["ship_reason", ["ship", 1, "code"], ["ship", 1, "reason"], True, "eq"],
        ]
    if item_id == "E-08":
        return [
            ["case_read", ["case", 1, "code"], ["unknown", 0, "code"], False, "eq"],
            ["evidence_count", ["evidence", 2, "available"], ["case", 1, "available"], False, "eq"],
            ["dup_count", ["dup", 3, "available"], ["evidence", 2, "available"], True, "eq"],
            ["late", ["late", 1, "code"], ["evidence", 1, "code"], False, "eq"],
            ["submit", ["submit", 2, "code"], ["late", 1, "code"], False, "eq"],
            ["submitted_read", ["submit", 3, "code"], ["evidence", 2, "code"], False, "eq"],
            ["submit_late", ["submitlate", 1, "code"], ["submit", 2, "code"], False, "eq"],
            ["after_evidence", ["after", 2, "code"], ["after", 1, "code"], False, "eq"],
            ["retry", ["retry", 2, "code"], ["retry", 1, "code"], True, "eq"],
            ["other_isolation", ["other", 3, "available"], ["case", 1, "available"], True, "eq"],
            ["kind", ["kind", 1, "code"], ["missingkind", 1, "code"], True, "eq"],
            ["default_kind", ["missingkind", 1, "code"], ["evidence", 1, "code"], True, "eq"],
            ["read_state", ["submit", 3, "code"], ["retry", 3, "code"], True, "eq"],
            ["case_code", ["case", 1, "code"], ["case", 1, "reason"], True, "eq"],
            ["unknown_reason", ["unknown", 0, "code"], ["unknown", 0, "reason"], True, "eq"],
            ["evidence_req", ["evidence", 1, "code"], ["late", 1, "code"], False, "eq"],
            ["submit_count", ["submit", 3, "available"], ["lit", 0], True, "eq"],
            ["closed_again", ["retry", 3, "code"], ["submit", 3, "code"], True, "eq"],
            ["duplicate_stable", ["dup", 2, "code"], ["evidence", 1, "code"], True, "eq"],
            ["deadline", ["submit", 2, "code"], ["submit", 2, "reason"], True, "eq"],
        ]
    if item_id == "E-09":
        return [
            ["claim", ["claim", 1, "code"], ["claim", 0, "code"], False, "eq"],
            ["available", ["claim", 1, "available"], ["renew", 1, "available"], False, "eq"],
            ["renew", ["renew", 1, "code"], ["old", 1, "code"], False, "eq"],
            ["old_worker", ["old", 1, "code"], ["expire", 1, "code"], False, "eq"],
            ["expired", ["expire", 1, "code"], ["boundary", 1, "code"], False, "eq"],
            ["boundary_read", ["boundary", 1, "available"], ["claim", 1, "available"], False, "eq"],
            ["maintain_read", ["maintain", 2, "code"], ["expire", 1, "code"], False, "eq"],
            ["maintain_claim", ["maintain_claim", 1, "code"], ["maintain", 2, "code"], True, "eq"],
            ["close_claim", ["close", 2, "code"], ["claim", 1, "code"], False, "eq"],
            ["retry", ["retry", 1, "code"], ["old", 1, "code"], False, "eq"],
            ["device_isolation", ["other", 1, "code"], ["expire", 1, "code"], True, "eq"],
            ["maintain_retry", ["maintain_retry", 1, "code"], ["maintain", 1, "code"], True, "eq"],
            ["claim_reason", ["claim", 1, "code"], ["claim", 1, "reason"], True, "eq"],
            ["read_valid", ["claim", 1, "code"], ["boundary", 1, "code"], True, "eq"],
            ["read_expired", ["expire", 1, "code"], ["expire", 1, "reason"], True, "eq"],
            ["maintain_disabled", ["close", 2, "code"], ["claim", 1, "code"], False, "eq"],
            ["ttl_change", ["renew", 1, "available"], ["claim", 1, "available"], False, "eq"],
            ["worker_code", ["old", 1, "code"], ["maintain_claim", 1, "code"], False, "eq"],
            ["request_stable", ["retry", 1, "available"], ["retry", 0, "available"], True, "eq"],
            ["maintenance_state", ["maintain", 1, "code"], ["maintain_retry", 1, "code"], True, "eq"],
        ]
    return [
        ["rate", ["rate", 2, "tax"], ["rate", 2, "gross"], False, "eq"],
        ["gross", ["rate", 2, "gross"], ["lit", 110], True, "eq"],
        ["items", ["items", 3, "tax"], ["rate", 2, "tax"], False, "eq"],
        ["round", ["round", 2, "tax"], ["lit", 3], True, "eq"],
        ["freeze", ["freeze", 4, "tax"], ["rate", 2, "tax"], True, "eq"],
        ["default", ["default", 2, "gross"], ["rate", 2, "gross"], True, "eq"],
        ["dup_item", ["dupitem", 3, "tax"], ["rate", 2, "tax"], True, "eq"],
        ["void_read", ["void", 4, "code"], ["void", 3, "code"], False, "eq"],
        ["void_issue", ["void_issue", 2, "code"], ["void", 3, "code"], False, "eq"],
        ["retry", ["retry", 2, "code"], ["retry", 1, "code"], True, "eq"],
        ["unknown", ["unknown", 0, "code"], ["void", 3, "code"], False, "eq"],
        ["region_tax", ["regions", 4, "tax"], ["regions", 5, "tax"], False, "eq"],
        ["region_gross", ["regions", 4, "gross"], ["regions", 5, "gross"], False, "eq"],
        ["rate_code", ["rate", 0, "code"], ["rate", 0, "reason"], True, "eq"],
        ["issue_code", ["rate", 2, "code"], ["rate", 2, "reason"], True, "eq"],
        ["void_code", ["void", 3, "code"], ["void", 3, "reason"], True, "eq"],
        ["draft_code", ["items", 1, "code"], ["items", 2, "code"], True, "eq"],
        ["freeze_issue", ["freeze", 2, "code"], ["rate", 2, "code"], True, "eq"],
        ["read_void", ["void", 4, "code"], ["void", 4, "reason"], True, "eq"],
        ["multi_region", ["regions", 4, "code"], ["regions", 5, "code"], True, "eq"],
    ]


PAIRS = {item: _make_pairs(item) for item in CASES}


def _cell(runs, spec):
    if spec[0] == "lit":
        return spec[1]
    rows = runs.get(spec[0])
    if not isinstance(rows, list):
        return None
    idx = spec[1]
    if idx < 0:
        idx += len(rows)
    if idx < 0 or idx >= len(rows) or not isinstance(rows[idx], dict):
        return None
    return rows[idx].get(spec[2])


def _judge(item_id, runs):
    covered, gaps, violations = [], [], []
    for name, left, right, same, mode in PAIRS[item_id]:
        a, b = _cell(runs, left), _cell(runs, right)
        if a is None or b is None:
            gaps.append(name)
            continue
        ok = (a == b) if same else (a != b)
        (covered if ok else violations).append(name if ok else "deduct_" + name)
    return {"covered": covered, "gaps": gaps, "violations": violations}


def fixture(marker: str, item_id: str) -> str:
    blob = json.dumps({item_id: CASES[item_id]}, ensure_ascii=False, separators=(",", ":"))
    pairs = json.dumps({item_id: PAIRS[item_id]}, ensure_ascii=False, separators=(",", ":"))
    cell = inspect.getsource(_cell)
    judge = inspect.getsource(_judge)
    return f'''import contextlib, copy, io, json
CASES=json.loads({blob!r}); PAIRS=json.loads({pairs!r})
{cell}
{judge}
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from solution import solve
runs={{}}
for name, events in CASES[{item_id!r}].items():
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            runs[name]=solve(copy.deepcopy(events))
    except BaseException:
        runs[name]=None
v=_judge({item_id!r}, runs)
print({marker!r}+" POINTS "+str(len(v["covered"]))+"/20")
print({marker!r}+" ENGINEERING "+json.dumps(v, ensure_ascii=False))
'''


def score_next(item_id: str, text: str):
    marker = "__MODEL_LENS_" + item_id.replace("-", "") + "_"
    with tempfile.TemporaryDirectory(prefix="engineering-next-") as directory:
        root = Path(directory)
        tests = root / "bank" / "tests"
        tests.mkdir(parents=True)
        (tests / "tests.py").write_text(fixture(marker, item_id), encoding="utf-8")
        grade = grade_response(Question(id=item_id, domain="engineering", difficulty="extreme", prompt="", grader={"type": "code_tests", "language": "python", "tests_file": "bank/tests/tests.py", "result_marker": marker}, pass_criteria="20 positive obligations and no negative debt", language="python"), text, repo_root=root)
    from .evaluation import unjudged_execution
    unavailable = unjudged_execution(grade)
    if unavailable is not None:
        return unavailable
    line = next((x for x in grade.detail.splitlines() if x.startswith("ENGINEERING ")), "")
    try:
        report = json.loads(line[len("ENGINEERING "):])
    except (ValueError, IndexError):
        report = {"covered": [], "violations": [], "gaps": ["execution_error"]}
    covered = sorted(set(report.get("covered", [])))
    violations = sorted(set(report.get("violations", [])))
    gaps = report.get("gaps", [])
    unobserved = len(set(gaps)) if isinstance(gaps, list) else 0
    return {"status": "pass" if len(covered) == LEDGER and not violations else "fail", "passed": len(covered) == LEDGER and not violations, "obligations": {"covered": len(covered), "total": LEDGER, "gap": LEDGER-len(covered), "unobserved": unobserved}, "obligations_covered": covered, "obligations_total": LEDGER, "prohibitions_total": LEDGER, "risk_debt": {"critical": 0, "high": 0, "medium": len(violations), "weighted_points": len(violations)}, "points": len(covered)-len(violations), "reason_code": "ok" if len(covered) == LEDGER and not violations else "content_mismatch", "positive_points": len(covered), "negative_points": len(violations), "net_points": len(covered)-len(violations), "prohibitions_triggered": violations, "reports": []}


REFS = {
    "E-07": '''def solve(events):
    batches, seen, held, out = {}, {}, set(), []
    def p(c, **x):
        r={"code":c,"reason":c}; r.update(x); return r
    for e in events:
        op=e.get("op"); b=e.get("batch")
        if op=="BATCH":
            if b not in batches: batches[b]={"qty":e.get("qty",10),"min":e.get("temp_min"),"max":e.get("temp_max"),"temp":e.get("temp")}
            else: batches[b]["temp"]=e.get("temp",batches[b].get("temp"))
            out.append(p("batch"))
        elif op=="SHIP":
            x=batches.get(b); rid=e.get("request_id")
            if rid in seen: out.append(seen[rid].copy()); continue
            t=e.get("temp", x.get("temp") if x else None)
            if x is None: r=p("missing")
            elif b in held: r=p("held")
            elif not isinstance(e.get("qty"),int) or e.get("qty")<=0 or x["qty"]<e["qty"]: r=p("rejected", available=x["qty"])
            elif t is None or t<x["min"] or t>x["max"]: r=p("temperature")
            else: x["qty"]-=e["qty"]; r=p("shipped", available=x["qty"])
            seen[rid]=r.copy(); out.append(r)
        elif op=="HOLD":
            if b not in batches: out.append(p("missing"))
            elif e.get("request_id") in held: out.append(p("duplicate"))
            else: held.add(b); out.append(p("held"))
        elif op=="READ":
            x=batches.get(b); out.append(p("missing") if x is None else p("held" if b in held else "ready", available=x["qty"]))
        else: out.append(p("ignored"))
    return out''',
    "E-08": '''def solve(events):
    cases, seen, out = {}, {}, []
    def p(c, **x):
        r={"code":c,"reason":c}; r.update(x); return r
    for e in events:
        op=e.get("op"); c=e.get("case")
        if op=="CASE":
            if c in cases: out.append(p("exists"))
            else: cases[c]={"deadline":e.get("deadline"),"ids":set(),"kept":{},"closed":False}; out.append(p("created"))
        elif op=="EVIDENCE":
            x=cases.get(c); rid=e.get("request_id")
            if x is None: r=p("missing")
            elif x["closed"]: r=p("closed")
            elif e.get("at",0)>=x["deadline"]: r=p("late")
            elif e.get("evidence_id") in x["ids"]: r=x["kept"][e.get("evidence_id")].copy()
            else: x["ids"].add(e.get("evidence_id")); r=p("accepted"); x["kept"][e.get("evidence_id")]=r.copy()
            if rid in seen: r=seen[rid].copy()
            elif rid is not None: seen[rid]=r.copy()
            out.append(r)
        elif op=="SUBMIT":
            x=cases.get(c); rid=e.get("request_id")
            if rid in seen: out.append(seen[rid].copy()); continue
            if x is None: r=p("missing")
            elif x["closed"]: r=p("closed")
            elif e.get("at",0)>x["deadline"]: r=p("late")
            else: x["closed"]=True; r=p("submitted", available=len(x["ids"]))
            if rid is not None: seen[rid]=r.copy()
            out.append(r)
        elif op=="READ":
            x=cases.get(c)
            if x is None: out.append(p("missing"))
            elif x["closed"]: out.append(p("closed", available=0))
            else: out.append(p("open", available=len(x["ids"])))
        else: out.append(p("ignored"))
    return out''',
    "E-09": '''def solve(events):
    leases, maint, seen, out = {}, {}, {}, []
    def p(c, **x):
        r={"code":c,"reason":c}; r.update(x); return r
    for e in events:
        d=e.get("device"); at=e.get("at",0); op=e.get("op"); key=e.get("request_id")
        x=leases.get(d)
        if x and at>=x["until"]: leases.pop(d,None); x=None
        if op=="MAINTAIN":
            if key in seen: out.append(seen[key].copy()); continue
            maint[d]=bool(e.get("enabled",True)); r=p("maintenance_on" if maint[d] else "maintenance_off"); seen[key]=r.copy(); out.append(r)
        elif op=="CLAIM":
            if key in seen: out.append(seen[key].copy()); continue
            if maint.get(d): r=p("maintenance")
            elif x is not None: r=p("busy")
            else: leases[d]={"worker":e.get("worker"),"until":at+e.get("ttl",0)}; r=p("claimed", available=e.get("ttl",0))
            seen[key]=r.copy(); out.append(r)
        elif op=="RENEW":
            if key in seen: out.append(seen[key].copy()); continue
            if maint.get(d): r=p("maintenance")
            elif x is None or x["worker"]!=e.get("worker"): r=p("not_owner")
            else: x["until"]=at+e.get("ttl",0); r=p("renewed", available=e.get("ttl",0))
            seen[key]=r.copy(); out.append(r)
        elif op=="READ":
            x=leases.get(d); out.append(p("maintenance") if maint.get(d) else (p("expired") if x is None else p("active", available=max(0,x["until"]-at))))
        else: out.append(p("ignored"))
    return out''',
    "E-10": '''def solve(events):
    rates, inv, idem, out = {}, {}, {}, []
    def p(c, **x):
        r={"code":c,"reason":c}; r.update(x); return r
    for e in events:
        op=e.get("op"); i=e.get("invoice"); rid=e.get("request_id")
        if op=="RATE": rates.setdefault(e.get("region","default"),{})[e.get("version")]=e.get("bps",0); out.append(p("rate"))
        elif op=="DRAFT":
            if rid in idem: out.append(idem[rid].copy()); continue
            x=inv.setdefault(i,{"region":e.get("region","default"),"items":{},"state":"draft"})
            if x["state"]!="draft": r=p("closed")
            elif e.get("item") in x["items"]: r=p("duplicate")
            else: x["items"][e.get("item")]=e.get("net",0); r=p("drafted")
            if rid is not None: idem[rid]=r.copy()
            out.append(r)
        elif op=="ISSUE":
            if rid in idem: out.append(idem[rid].copy()); continue
            x=inv.get(i)
            if x is None: r=p("missing")
            elif x["state"]!="draft": r=p("closed")
            else:
                bps=max(rates.get(x["region"],{0:0}).values(),default=0); tax=sum(n*bps//10000 for n in x["items"].values()); x.update(state="issued",tax=tax,gross=sum(x["items"].values())+tax); r=p("issued",tax=tax,gross=x["gross"])
            if rid is not None: idem[rid]=r.copy()
            out.append(r)
        elif op=="VOID":
            if rid in idem: out.append(idem[rid].copy()); continue
            x=inv.get(i); r=p("missing") if x is None else (p("voided") if x["state"]=="issued" else p("rejected"));
            if x is not None and x["state"]=="issued": x["state"]="void"
            if rid is not None: idem[rid]=r.copy()
            out.append(r)
        elif op=="READ":
            x=inv.get(i); out.append(p("missing") if x is None else p(x["state"], **({"tax":x.get("tax"),"gross":x.get("gross")} if x.get("state") in ("issued","void") else {})))
        else: out.append(p("ignored"))
    return out''',
}
