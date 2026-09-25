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


E01_PROMPT = """工程题 E-01：为一个 SaaS 管理后台实现账号登录组件。

评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供
def solve(events)，接收 JSON 兼容的事件列表，返回同长度的 JSON 兼容结果列表。
事件按输入顺序处理；每个事件都有 id、op、now（整数）。公开事件为 REGISTER、LOGIN、
REQUEST、LOGOUT。REGISTER 带 user、password；LOGIN 带 user、password，可带 request_id；
REQUEST/LOGOUT 带 session 或 session_ref。session_ref 是前面某个 LOGIN 事件的 id，
表示使用该事件结果中的 session。LOGIN 成功时应返回后续事件可使用的 session。

客户端可能因网络重试而重复提交同一个 request_id；时间只取事件中的 now，不读取系统
时钟。组件运行在不可信客户端前面。不得使用网络、文件、工具或子进程。不要输出解释，
只输出一个 python 代码围栏。"""


# These are product-shaped scenarios, not labels shown to the candidate.
E02_PROMPT = """工程题 E-02：实现支付服务的 webhook 接收器。

提供 solve(events)，事件按到达顺序处理并返回同长度结果。事件为 CREATE、CALLBACK、GET；
回调包含 merchant、order、amount、state、event_id、signature、now。回调可能重复、乱序、
延迟或签名错误，merchant 与 order 共同标识订单。状态只能按支付业务规则推进，查询结果
必须稳定。不要使用网络、文件、工具或子进程，只输出 python 代码围栏。"""
E03_PROMPT = """工程题 E-03：实现多租户库存预占组件。

提供 solve(events)，事件为 STOCK、RESERVE、CONFIRM、RELEASE、EXPIRE、GET；事件包含 tenant、
sku、quantity、reservation_id、request_id、now。请求可能重试，确认、释放和超时可能交叉；
同一商品不能超卖，租户和商品不能串线。不要使用网络、文件、工具或子进程，只输出 python
代码围栏。"""
E04_PROMPT = """工程题 E-04：实现多租户文档归档与抹除组件。

提供 solve(events)，事件为 PUT、READ、ERASE、CHARGE、AUDIT；事件包含 tenant、doc_id、content、
amount、request_id、now。抹除与读取、账务和审计可能交错，删除请求可能重试，同名 id 可出现在
不同租户。普通读取、账务核对和操作审计要各自保持一致。不要使用网络、文件、工具或子进程，
只输出 python 代码围栏。"""
E05_PROMPT = """工程题 E-05：实现多租户异步任务调度器。

提供 solve(events)，事件为 SUBMIT、START、COMPLETE、FAIL、CANCEL、GET；事件包含 tenant、task_id、
depends_on、attempt、request_id、now。worker 可能重复回报、暂时失联或使用旧顺序；任务有依赖、
重试、取消和租户并发额度。不要使用网络、文件、工具或子进程，只输出 python 代码围栏。"""
E06_PROMPT = """工程题 E-06：实现多环境配置发布组件。

提供 solve(events)，事件为 PROPOSE、APPROVE、PUBLISH、READ、ROLLBACK；事件包含 env、key、version、
value、request_id、now、approved。发布可能乱序重复，存在灰度环境和旧客户端；回滚后读取应稳定，
环境之间不能相互污染。不要使用网络、文件、工具或子进程，只输出 python 代码围栏。"""

ENGINEERING_SCENARIOS = {
    "E-01": {"title": "SaaS 后台账号登录", "status": "runnable", "prompt": E01_PROMPT},
    "E-02": {"title": "支付回调接收器", "status": "runnable", "prompt": E02_PROMPT},
    "E-03": {"title": "库存预占与超卖保护", "status": "runnable", "prompt": E03_PROMPT},
    "E-04": {"title": "文档抹除与审计留存", "status": "runnable", "prompt": E04_PROMPT},
    "E-05": {"title": "异步任务调度器", "status": "runnable", "prompt": E05_PROMPT},
    "E-06": {"title": "配置发布与回滚", "status": "runnable", "prompt": E06_PROMPT},
}


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
        {"id": "out", "op": "LOGOUT", "session_ref": "l2", "now": 4},
        {"id": "after", "op": "REQUEST", "session_ref": "l2", "now": 5},
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
)


def _digest(value):
    import hashlib
    return hashlib.sha256(str(value).encode()).hexdigest()


def login_reference(events):
    users, sessions, failed, idem, by_id = {}, {}, {}, {}, {}
    out, counter = [], 0

    def result(ok, **extra):
        return {"ok": bool(ok), **extra}

    def token_for(event):
        if event.get("session_ref") is not None:
            prior = by_id.get(event["session_ref"])
            return prior.get("session") if isinstance(prior, dict) else None
        return event.get("session")

    for event in events:
        op, user, now = event.get("op"), event.get("user"), int(event.get("now", 0))
        if op == "REGISTER":
            users[user] = {"digest": _digest(event.get("password", "")), "locked_until": 0}
            failed[user] = 0
            response = result(True)
        elif op == "LOGIN":
            key = event.get("request_id")
            if key is not None and (user, key) in idem:
                response = copy.deepcopy(idem[user, key])
            else:
                record, password = users.get(user), event.get("password", "")
                valid = record is not None and now >= record["locked_until"] and _digest(password) == record["digest"]
                if not valid:
                    if record is not None and now >= record["locked_until"] and _digest(password) != record["digest"]:
                        failed[user] += 1
                        if failed[user] >= 5:
                            record["locked_until"] = now + 30
                    response = result(False, error="INVALID_CREDENTIALS")
                else:
                    failed[user] = 0
                    counter += 1
                    token = f"session-{counter}"
                    sessions[token] = {"user": user, "active": True}
                    response = result(True, session=token)
                if key is not None:
                    idem[user, key] = copy.deepcopy(response)
        elif op == "REQUEST":
            token = token_for(event)
            response = result(bool(token in sessions and sessions[token]["active"]))
        elif op == "LOGOUT":
            token = token_for(event)
            if token in sessions:
                sessions[token]["active"] = False
            response = result(True)
        else:
            response = result(False, error="INVALID_EVENT")
        out.append(response)
        if isinstance(event.get("id"), str):
            by_id[event["id"]] = response
    return out


def _report(name, events, output):
    rows = output if isinstance(output, list) else []
    raw = json.dumps(output, ensure_ascii=False, sort_keys=True, default=str)
    ok = [row.get("ok") if isinstance(row, dict) else None for row in rows]
    covered, gaps, violations = [], [], []
    if len(rows) != len(events):
        gaps.append("response_shape")
    else:
        covered.append("response_shape")
    if name == "basic_flow":
        (covered if len(rows) >= 3 and ok[1] is True and ok[2] is True else gaps).append("basic_correctness")
    elif name == "failure_equivalence":
        if len(rows) >= 3 and ok[1] is False and ok[2] is False:
            a = {k: v for k, v in rows[1].items() if k not in {"trace", "session"}}
            b = {k: v for k, v in rows[2].items() if k not in {"trace", "session"}}
            (covered if a == b else violations).append("failure_equivalence" if a == b else "failure_disclosure")
        else:
            gaps.append("failure_equivalence")
    elif name == "secret_boundary":
        if len(rows) >= 2 and ok[1] is True and "secret-456" not in raw:
            covered.append("response_secret_not_echoed")
        elif "secret-456" in raw:
            violations.append("secret_exposure")
        else:
            gaps.append("response_secret_not_echoed")
    elif name == "lock_recovery":
        if len(rows) >= 13 and ok[-2] is False and ok[-1] is True:
            covered.append("temporary_lock_recovery")
        elif ok and ok[-1] is False:
            violations.append("permanent_lock")
        else:
            gaps.append("temporary_lock_recovery")
    elif name == "session_lifecycle":
        tokens = [r.get("session") for r in rows if isinstance(r, dict) and r.get("session")]
        if len(tokens) >= 2 and tokens[-1] != tokens[-2]:
            covered.append("session_rotation")
        else:
            gaps.append("session_rotation")
        if len(rows) >= 6 and ok[3] is True and ok[5] is False:
            covered.append("logout_revocation")
        elif len(rows) >= 6 and ok[5] is True:
            violations.append("logout_bypass")
        else:
            gaps.append("logout_revocation")
    elif name == "idempotent_retry":
        tokens = [r.get("session") for r in rows if isinstance(r, dict) and r.get("session")]
        (covered if len(tokens) == 2 and tokens[0] == tokens[1] else gaps).append("idempotent_retry")
    elif name == "account_isolation":
        (covered if ok and ok[-1] is True else gaps).append("account_isolation")
    elif name == "malformed_input":
        if len(rows) == 3 and ok[1] is False and ok[2] is False:
            covered.append("invalid_input_fail_closed")
        else:
            violations.append("invalid_input_fail_open")
    return {"covered": covered, "gaps": gaps, "violations": violations}


def engineering_result_fixture(marker):
    blob = json.dumps(_SCENARIOS, ensure_ascii=False, separators=(",", ":"))
    evaluator = inspect.getsource(_report)
    return f'''import contextlib, copy, io, json
{evaluator}
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from solution import solve
scenarios = json.loads({blob!r})
reports = []
for scenario in scenarios:
    events = copy.deepcopy(scenario["events"])
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            output = solve(events)
    except BaseException:
        output = None
    reports.append({{"name": scenario["name"], **_report(scenario["name"], events, output)}})
covered = sorted({{x for r in reports for x in r["covered"]}})
gaps = sorted({{x for r in reports for x in r["gaps"]}})
violations = sorted({{x for r in reports for x in r["violations"]}})
print({marker!r} + " POINTS " + str(len(covered)) + "/10")
print({marker!r} + " ENGINEERING " + json.dumps({{"covered": covered, "gaps": gaps, "violations": violations, "reports": reports}}, ensure_ascii=False, sort_keys=True))
'''


def reference_source(item_id="E-01"):
    digest = inspect.getsource(_digest)
    source = inspect.getsource(login_reference)
    if item_id == "E-01":
        return "import copy\n" + digest + "\n" + source.replace("def login_reference", "def solve", 1)
    from .engineering_extra import REFS
    return REFS[item_id]


_RISK_WEIGHTS = {"critical": 6, "high": 3, "medium": 1}


def aggregate_engineering(results):
    """汇总工程栏自身的 10 点题目；不折算成 0-100，也不跨栏合成。"""
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
    line = next((line for line in grade.detail.splitlines() if line.startswith("ENGINEERING ")), "")
    try:
        report = json.loads(line[len("ENGINEERING "):])
    except (ValueError, TypeError):
        report = {"covered": [], "gaps": [], "violations": [], "unobserved": ["fixture_or_execution_error"], "reports": []}
    covered = sorted(set(report.get("covered", [])))
    gaps = sorted(set(report.get("gaps", [])))
    violations = sorted(set(report.get("violations", [])))
    unobserved = sorted(set(report.get("unobserved", [])))
    risk_debt = {"critical": 0, "high": 0, "medium": 0}
    for violation in violations:
        if violation in {"secret_exposure", "invalid_input_fail_open"}:
            risk_debt["critical"] += 1
        elif violation in {"logout_bypass", "permanent_lock"}:
            risk_debt["high"] += 1
        elif violation == "failure_disclosure":
            risk_debt["medium"] += 1
    weighted = sum(risk_debt[k] * _RISK_WEIGHTS[k] for k in risk_debt)
    total = 10
    negative_points = len(violations)
    net_points = len(covered) - negative_points
    return {
        "status": "pass" if len(covered) == total and not violations else "fail",
        "passed": len(covered) == total and not violations,
        "obligations": {"covered": len(covered), "total": total, "gap": len(gaps), "unobserved": len(unobserved)},
        "obligations_covered": covered, "obligations_total": total,
        "prohibitions_triggered": violations, "prohibitions_total": 3,
        "risk_debt": {**risk_debt, "weighted_points": weighted},
        "positive_points": len(covered), "negative_points": negative_points,
        "net_points": net_points,
        "unobserved_reasons": unobserved,
        "reports": report.get("reports", []),
    }
