"""工程能力题：公开业务协议，隐藏评分账。

工程题独立于推理/编码栏，不产生全库 0-100 总分。夹具只判断黑盒可观察行为；
不能从黑盒证明的内部实现不计入义务账。
"""

from __future__ import annotations

import copy
import inspect
import json
import secrets
import tempfile
from pathlib import Path

from src.grade import grade_response
from src.types import Question

# 题面只留愿望和接口。考察点在隐藏场景里。改接口或隐藏场景前先升版本。
ENGINEERING_VERSION = "v3.3"

_CODE_RULE = "每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。"


def _wish(title, interface):
    return f"""工程题 {title}。

{interface}
{_CODE_RULE}

评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供 def solve(events)。它接收 JSON 兼容的事件列表，按输入顺序处理，返回同样长度的 JSON 兼容结果列表。不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。"""


E01_PROMPT = """工程题 E-01：为一个 SaaS 管理后台做一套生产级别可用的注册和登录。

评测会把你的代码写入 solution.py，并执行 from solution import solve。
必须提供 def solve(events)，接收 JSON 兼容的事件列表，返回同长度的 JSON 兼容结果列表。
事件按输入顺序处理；每个事件都有 id、op、now（整数）。时间只看事件里的 now。
op 为 REGISTER、LOGIN、REQUEST。
REGISTER 带 user、password，可以带 generation：不带 generation 是老用户，generation 为 2 是新用户。
LOGIN 带 user、password，可以带 request_id 和 client：legacy 是老客户端，current 是新客户端，不带 client 时视为 current。
REQUEST 带 session，或者带 session_ref，可以带 client。不带 client 时视为不限制。
session_ref 是前面某个 LOGIN 事件的 id，表示用那次登录结果里的 session。
LOGIN 成功时，结果里要有后续事件能用的 session。
每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。

不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。"""


E02_PROMPT = _wish("E-02：做一个生产级别可用的支付通知接收组件，商户要能查订单付没付", """事件是对象，带 op。订单由 merchant 和 order 标识。
CREATE 带 amount（整数）和 fee_rule：flat 或 surcharge，不带 fee_rule 时视为 flat。
CALLBACK 带 amount、state、event_id，可以带 signature 和 notice_version。state 只能是 PAID 或 REFUNDED。notice_version 不带时视为 2。
GET 也是一次事件。""")
E03_PROMPT = _wish("E-03：做一个生产级别可用的库存预占组件，要能查某个买家现在能买多少", """事件是对象，带 op，并带 tenant 和 sku。
STOCK 带 quantity、pool、batch，可以带 expire_at。pool 是 open 或 holdback。batch 是 old 或 new。
RESERVE 带 quantity、reservation_id、buyer、now。buyer 是 new 或 returning。
GET 带 buyer 和 now，结果里用 available 表示这个买家此刻能买的件数。""")
E04_PROMPT = _wish("E-04：做一个生产级别可用的文档归档组件，文档可以写入和抹掉，财务要能核对入账", """事件是对象，带 op，并带 tenant 和 doc_id。
PUT 带 content，可以带 amount 和 retention。retention 是 normal 或 hold，不带时视为 normal。
ERASE 带 request_id。
READ 带 role：user 或 auditor。结果里可以带 amount。""")
E05_PROMPT = _wish("E-05：做一个生产级别可用的多租户异步任务组件，工人会回报执行结果", """事件是对象，带 op、tenant 和 task_id。
SUBMIT 可以带 depends_on，值是同一租户的另一个 task_id。
UPDATE 带 action：start、complete、fail 或 cancel，并带 protocol 和 attempt。protocol 不带时视为 2。
GET 也是一次事件。""")
E06_PROMPT = _wish("E-06：做一个生产级别可用的配置发布组件，配置按环境发布，并且可以回到旧版本", """事件是对象，带 op、env 和 key。
PROPOSE 带 version、value，可以带 request_id、min_client 和 approved。version、min_client 是整数，min_client 不带时视为 1。
PUBLISH 带 version，也可以带 rollback_to。
READ 可以带 client（整数），不带时视为不限制。读到已发布的内容时，把那份内容放在 value 里。""")

ENGINEERING_SCENARIOS = {
    "E-01": {"title": "注册与登录", "status": "runnable", "prompt": E01_PROMPT},
    "E-02": {"title": "支付通知", "status": "runnable", "prompt": E02_PROMPT},
    "E-03": {"title": "库存预占", "status": "runnable", "prompt": E03_PROMPT},
    "E-04": {"title": "文档归档", "status": "runnable", "prompt": E04_PROMPT},
    "E-05": {"title": "异步任务", "status": "runnable", "prompt": E05_PROMPT},
    "E-06": {"title": "配置发布", "status": "runnable", "prompt": E06_PROMPT},
}
import re as _re
from .next_questions import _sections, DOCS as _NEXT_DOCS


def _published_wish(body: str) -> str:
    # 文档整节还含评分表和参考行为。发给模型的只有题面全文。
    match = _re.search(r"\*\*题面全文。\*\*\s*(.+?)(?:\n\*\*|\Z)", body, _re.S)
    if match is None:
        raise KeyError("题面全文")
    return match.group(1).strip()


for _item_id, (_title, _body) in _sections(_NEXT_DOCS["engineering"], "E").items():
    if _item_id not in ENGINEERING_SCENARIOS:
        ENGINEERING_SCENARIOS[_item_id] = {"title": _title, "status": "runnable", "prompt": _published_wish(_body)}


_SCENARIOS = (
    {"name": "basic_flow", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "l", "op": "LOGIN", "user": "alice", "password": "pw", "now": 1},
        {"id": "q", "op": "REQUEST", "session_ref": "l", "now": 2},
    ]},
    {"name": "failure_equivalence", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "u", "op": "LOGIN", "user": "ghost", "password": "pw", "now": 1},
        {"id": "p", "op": "LOGIN", "user": "alice", "password": "bad", "now": 2},
    ]},
    {"name": "secret_boundary", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "secret-456", "now": 0},
        {"id": "l", "op": "LOGIN", "user": "alice", "password": "secret-456", "now": 1},
        {"id": "f", "op": "LOGIN", "user": "alice", "password": "bad", "now": 2},
    ]},
    {"name": "lock_recovery", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        *({"id": f"f{i}", "op": "LOGIN", "user": "alice", "password": "bad", "now": i} for i in range(1, 11)),
        {"id": "during", "op": "LOGIN", "user": "alice", "password": "pw", "now": 11},
        {"id": "after", "op": "LOGIN", "user": "alice", "password": "pw", "now": 100},
    ]},
    {"name": "session_lifecycle", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "l1", "op": "LOGIN", "user": "alice", "password": "pw", "now": 1},
        {"id": "l2", "op": "LOGIN", "user": "alice", "password": "pw", "now": 2},
        {"id": "before", "op": "REQUEST", "session_ref": "l2", "now": 3},
    ]},
    {"name": "idempotent_retry", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "a", "op": "LOGIN", "user": "alice", "password": "pw", "request_id": "x", "now": 1},
        {"id": "b", "op": "LOGIN", "user": "alice", "password": "pw", "request_id": "x", "now": 2},
    ]},
    {"name": "account_isolation", "events": [
        {"id": "a", "op": "REGISTER", "user": "alice", "password": "alice-pw", "now": 0},
        {"id": "b", "op": "REGISTER", "user": "bob", "password": "bob-pw", "now": 0},
        *({"id": f"fa{i}", "op": "LOGIN", "user": "alice", "password": "bad", "now": i} for i in range(1, 11)),
        {"id": "lb", "op": "LOGIN", "user": "bob", "password": "bob-pw", "now": 11},
    ]},
    {"name": "malformed_input", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "x", "op": "UNKNOWN", "now": 1},
        {"id": "y", "op": "REQUEST", "session": "forged", "now": 2},
    ]},
    {"name": "duplicate_register", "events": [
        {"id": "r1", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "r2", "op": "REGISTER", "user": "alice", "password": "pw", "now": 1},
    ]},
    {"name": "current_new", "events": [
        {"id": "r", "op": "REGISTER", "user": "nina", "password": "pw", "generation": 2, "now": 0},
        {"id": "l", "op": "LOGIN", "user": "nina", "password": "pw", "client": "current", "now": 1},
        {"id": "q", "op": "REQUEST", "session_ref": "l", "now": 2},
    ]},
    {"name": "legacy_new", "events": [
        {"id": "r", "op": "REGISTER", "user": "nina", "password": "pw", "generation": 2, "now": 0},
        {"id": "l", "op": "LOGIN", "user": "nina", "password": "pw", "client": "legacy", "now": 1},
        {"id": "q", "op": "REQUEST", "session_ref": "l", "now": 2},
    ]},
    {"name": "legacy_old", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "l", "op": "LOGIN", "user": "alice", "password": "pw", "client": "legacy", "now": 1},
        {"id": "q", "op": "REQUEST", "session_ref": "l", "now": 2},
    ]},
    {"name": "cross_request", "events": [
        {"id": "ra", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "la", "op": "LOGIN", "user": "alice", "password": "pw", "request_id": "x", "now": 1},
        {"id": "rb", "op": "REGISTER", "user": "bob", "password": "bob", "now": 2},
        {"id": "lb", "op": "LOGIN", "user": "bob", "password": "bob", "request_id": "x", "now": 3},
    ]},
    {"name": "client_bind", "events": [
        {"id": "r", "op": "REGISTER", "user": "alice", "password": "pw", "now": 0},
        {"id": "l", "op": "LOGIN", "user": "alice", "password": "pw", "client": "legacy", "now": 1},
        {"id": "bad", "op": "REQUEST", "session_ref": "l", "client": "current", "now": 2},
        {"id": "ok", "op": "REQUEST", "session_ref": "l", "client": "legacy", "now": 3},
    ]},
)


def _digest(value):
    import hashlib
    return hashlib.sha256(str(value).encode()).hexdigest()


def login_reference(events):
    users, sessions, failed, idem, by_id = {}, {}, {}, {}, {}
    out, counter = [], 0

    def result(ok, code, **extra):
        return {"ok": bool(ok), "code": code, "reason": code, **extra}

    def token_for(event):
        if event.get("session_ref") is not None:
            prior = by_id.get(event["session_ref"])
            return prior.get("session") if isinstance(prior, dict) else None
        return event.get("session")

    for event in events:
        op, user, now = event.get("op"), event.get("user"), int(event.get("now", 0))
        if op == "REGISTER":
            if user in users:
                response = result(False, "already_registered")
            else:
                users[user] = {"digest": _digest(event.get("password", "")), "locked_until": 0, "generation": event.get("generation", 1)}
                failed[user] = 0
                response = result(True, "registered")
        elif op == "LOGIN":
            key = event.get("request_id")
            if key is not None and (user, key) in idem:
                response = copy.deepcopy(idem[user, key])
            else:
                record, password = users.get(user), event.get("password", "")
                client = event.get("client", "current")
                if record is not None and client == "legacy" and record["generation"] == 2:
                    response = result(False, "legacy_blocked")
                elif record is not None and now < record["locked_until"]:
                    response = result(False, "locked")
                elif record is None:
                    response = result(False, "unknown_user")
                elif _digest(password) != record["digest"]:
                    failed[user] += 1
                    if failed[user] >= 5:
                        record["locked_until"] = now + 30
                    response = result(False, "bad_credentials")
                else:
                    failed[user] = 0
                    counter += 1
                    token = f"session-{counter}"
                    sessions[token] = {"user": user, "active": True, "client": client}
                    kind = "logged_in_legacy" if client == "legacy" else ("logged_in_new" if record["generation"] == 2 else "logged_in_old")
                    response = result(True, kind, session=token)
                if key is not None:
                    idem[user, key] = copy.deepcopy(response)
        elif op == "REQUEST":
            token = token_for(event)
            record = sessions.get(token)
            asked = event.get("client")
            if record is not None and record["active"] and asked not in (None, record["client"]):
                response = result(False, "client_mismatch")
            elif record is not None and record["active"]:
                response = result(True, "session_ok")
            elif record is not None:
                response = result(False, "session_revoked")
            else:
                response = result(False, "session_unknown")
        elif op == "LOGOUT":
            token = token_for(event)
            if token in sessions and sessions[token]["active"]:
                sessions[token]["active"] = False
                response = result(True, "logged_out")
            else:
                response = result(False, "session_unknown")
        else:
            response = result(False, "invalid_event")
        out.append(response)
        if isinstance(event.get("id"), str):
            by_id[event["id"]] = response
    return out


def judge_login(outputs):
    def cell(spec):
        if spec[0] == "lit":
            return spec[1]
        name, index, field = spec
        rows = outputs.get(name)
        if not isinstance(rows, list):
            return None
        if field == "blob":
            return json.dumps(rows, ensure_ascii=False, default=str)
        if index < 0:
            index += len(rows)
        if index < 0 or index >= len(rows) or not isinstance(rows[index], dict):
            return None
        return rows[index].get(field)

    pairs = [
        ("login_vs_bad", ("basic_flow", 1, "code"), ("failure_equivalence", 2, "code"), False, "eq"),
        ("bad_vs_unknown", ("failure_equivalence", 2, "code"), ("failure_equivalence", 1, "code"), False, "eq"),
        ("bad_reason", ("failure_equivalence", 2, "reason"), ("failure_equivalence", 1, "reason"), False, "eq"),
        ("locked_vs_ok", ("lock_recovery", -2, "code"), ("basic_flow", 1, "code"), False, "eq"),
        ("locked_vs_later", ("lock_recovery", -2, "code"), ("lock_recovery", -1, "code"), False, "eq"),
        ("cross_ok", ("cross_request", 3, "code"), ("basic_flow", 1, "code"), True, "eq"),
        ("gen_codes", ("current_new", 1, "code"), ("basic_flow", 1, "code"), False, "eq"),
        ("both_work", ("current_new", 2, "code"), ("basic_flow", 2, "code"), True, "eq"),
        ("legacy_blocks", ("legacy_new", 1, "code"), ("current_new", 1, "code"), False, "eq"),
        ("legacy_dead", ("legacy_new", 2, "code"), ("basic_flow", 2, "code"), False, "eq"),
        ("client_diff", ("legacy_old", 1, "code"), ("basic_flow", 1, "code"), False, "eq"),
        ("client_use", ("client_bind", 2, "code"), ("client_bind", 3, "code"), False, "eq"),
        ("client_ok", ("client_bind", 3, "code"), ("basic_flow", 2, "code"), True, "eq"),
        ("forged", ("malformed_input", 2, "code"), ("session_lifecycle", 3, "code"), False, "eq"),
        ("dup_register", ("duplicate_register", 1, "code"), ("duplicate_register", 0, "code"), False, "eq"),
        ("retry_code", ("idempotent_retry", 1, "code"), ("idempotent_retry", 2, "code"), True, "eq"),
        ("retry_session", ("idempotent_retry", 1, "session"), ("idempotent_retry", 2, "session"), True, "eq"),
        ("bob_ok", ("account_isolation", -1, "code"), ("basic_flow", 1, "code"), True, "eq"),
        ("no_secret", ("secret_boundary", 0, "blob"), ("lit", "secret-456"), False, "contains"),
        ("cross_session", ("cross_request", 1, "session"), ("cross_request", 3, "session"), False, "eq"),
    ]
    covered, gaps, violations = [], [], []
    for name, left, right, same, mode in pairs:
        got, want = cell(left), cell(right)
        if got is None or want is None:
            gaps.append(name)
            continue
        if mode == "contains":
            ok = (str(want) in str(got)) if same else (str(want) not in str(got))
        else:
            ok = (got == want) if same else (got != want)
        if ok:
            covered.append(name)
        else:
            violations.append("deduct_" + name)
    return {"covered": covered, "gaps": gaps, "violations": violations}


def engineering_result_fixture(marker):
    blob = json.dumps(_SCENARIOS, ensure_ascii=False, separators=(",", ":"))
    evaluator = inspect.getsource(judge_login)
    return f'''import contextlib, copy, io, json
{evaluator}
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from solution import solve
scenarios = json.loads({blob!r})
outputs = {{}}
for scenario in scenarios:
    events = copy.deepcopy(scenario["events"])
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            output = solve(events)
    except BaseException:
        output = None
    outputs[scenario["name"]] = output
verdict = judge_login(outputs)
print({marker!r} + " POINTS " + str(len(verdict["covered"])) + "/20")
print({marker!r} + " ENGINEERING " + json.dumps(verdict, ensure_ascii=False, sort_keys=True))
'''


def reference_source(item_id="E-01"):
    digest = inspect.getsource(_digest)
    source = inspect.getsource(login_reference)
    if item_id == "E-01":
        return "import copy\n" + digest + "\n" + source.replace("def login_reference", "def solve", 1)
    if item_id in {"E-07", "E-08", "E-09", "E-10"}:
        from .engineering_next import REFS
        return REFS[item_id]
    from .engineering_extra import REFS
    return REFS[item_id]


def aggregate_engineering(results):
    """汇总工程栏自身的 20 点题目；不折算成 0-100，也不跨栏合成。"""
    rows = [row for row in results if isinstance(row, dict)]
    positive = sum(int(row.get("positive_points", 0)) for row in rows)
    negative = sum(int(row.get("negative_points", 0)) for row in rows)
    total = sum(int((row.get("obligations") or {}).get("total", 0)) for row in rows)
    strict = sum(row.get("passed") is True for row in rows)
    return {
        "questions": len(rows),
        "max_positive_points": total,
        "positive_points": positive,
        "negative_points": negative,
        "net_points": positive - negative,
        "strict_passed": strict,
    }


def score_engineering(text, item_id="E-01"):
    if item_id != "E-01":
        if item_id in {"E-07", "E-08", "E-09", "E-10"}:
            from .engineering_next import score_next
            return score_next(item_id, text)
        from .engineering_extra import score_extra
        return score_extra(item_id, text)
    marker = "__MODEL_LENS_E01_" + secrets.token_hex(12) + "__"
    with tempfile.TemporaryDirectory(prefix="engineering-grade-") as temporary:
        root = Path(temporary)
        tests_dir = root / "bank" / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "tests.py").write_text(engineering_result_fixture(marker), encoding="utf-8")
        question = Question(
            id="E-01", domain="engineering", difficulty="extreme", prompt=E01_PROMPT,
            grader={"type": "code_tests", "language": "python", "tests_file": "bank/tests/tests.py", "result_marker": marker},
            pass_criteria="observable obligations covered and no risk debt", language="python",
        )
        grade = grade_response(question, text, repo_root=root)
    from .evaluation import unjudged_execution
    unavailable = unjudged_execution(grade)
    if unavailable is not None:
        return unavailable
    line = next((line for line in grade.detail.splitlines() if line.startswith("ENGINEERING ")), "")
    try:
        report = json.loads(line[len("ENGINEERING "):])
    except (ValueError, TypeError):
        report = {"covered": [], "gaps": [], "violations": [], "unobserved": ["fixture_or_execution_error"], "reports": []}
    covered = sorted(set(report.get("covered", [])))
    gaps = sorted(set(report.get("gaps", [])))
    violations = sorted(set(report.get("violations", [])))
    unobserved = sorted(set(report.get("unobserved", [])))
    positive, negative_points = len(covered), len(violations)
    return {
        "status": "pass" if positive == 20 and negative_points == 0 else "fail",
        "passed": positive == 20 and negative_points == 0,
        "obligations": {"covered": positive, "total": 20, "gap": 20 - positive, "unobserved": len(unobserved)},
        "obligations_covered": covered, "obligations_total": 20,
        "prohibitions_triggered": violations, "prohibitions_total": 20,
        "risk_debt": {"critical": 0, "high": 0, "medium": negative_points, "weighted_points": negative_points},
        "points": positive - negative_points,
        "reason_code": "ok" if positive == 20 and negative_points == 0 else "content_mismatch",
        "positive_points": positive, "negative_points": negative_points,
        "net_points": positive - negative_points,
        "unobserved_reasons": unobserved,
        "reports": report.get("reports", []),
    }
